import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load .env file from backend directory if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path, override=True)

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.auth import (
    create_or_update_google_user,
    create_session,
    delete_session,
    get_current_user,
    get_optional_user,
    update_user_profile,
    verify_google_id_token,
)
from backend.llm import validate_llm_env
from backend.memory import retrieve_context
from backend.recognize import recognize_image
from backend.schemas import (
    AuthResponse,
    GoogleAuthRequest,
    ProfileUpdateRequest,
    RecognizeRequest,
    RecognizeResponse,
    RetrieveRequest,
    RetrieveResponse,
    SolveRequest,
    SolveResponse,
    STTRequest,
    STTResponse,
    TTSRequest,
    TTSStatusResponse,
    UserResponse,
)
from backend.solver import solve_problem
from backend.tts import (
    TTSAllProvidersFailed,
    generate_tts_wav,
    get_tts_config,
    transcribe_speech_gnani,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify required environment variables on startup unless explicitly in test mode
    if os.environ.get("TEST_MODE") != "true":
        try:
            validate_llm_env()
        except Exception as exc:
            logger.warning(f"[STARTUP WARNING] LLM environment check: {exc}")
    yield
    from backend.verify import shutdown_sympy_worker_pool
    shutdown_sympy_worker_pool()


app = FastAPI(
    title="InkMentor Math Solver API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)


@app.middleware("http")
async def vercel_path_rewrite_middleware(request: Request, call_next):
    """Normalizes path if Vercel serverless gateway passes the script name or rewrites stripped prefix."""
    path = request.scope.get("path", "")
    if path in ("/api/index.py", "/api/index", "/index.py", "/api"):
        matched = request.headers.get("x-matched-path") or request.headers.get("x-forwarded-uri")
        if matched:
            request.scope["path"] = matched.split("?")[0]
    return await call_next(request)


# CORS configuration
default_origins = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000,null"
allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", default_origins)
origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Server-Timing",
        "X-TTS-Provider",
        "X-TTS-Duration-Ms",
        "X-TTS-Attempts",
        "X-Trace-Id",
    ],
)



# Static paths for local development and fallback serving
PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public"))
HTML_PATH = os.path.join(PUBLIC_DIR, "index.html")
if not os.path.exists(HTML_PATH):
    HTML_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "InkMentor.html"))

FONTS_DIR = os.path.join(PUBLIC_DIR, "fonts")
if not os.path.exists(FONTS_DIR):
    FONTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fonts"))


def get_client_ip(req: Request) -> str:
    """Resolves client IP, trusting proxy forwarded headers only when TRUST_PROXY_HEADERS is true."""
    trust_proxy = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() in ("true", "1", "yes")
    if trust_proxy:
        forwarded = req.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = req.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    if req.client and req.client.host:
        return req.client.host
    return "127.0.0.1"


@app.get("/")
@app.get("/InkMentor.html")
@app.get("/index.html")
async def serve_index():
    if os.path.exists(HTML_PATH):
        return FileResponse(
            HTML_PATH,
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return JSONResponse(
        status_code=404,
        content={"detail": "index.html not found"},
    )


@app.api_route("/fonts/{font_name}", methods=["GET", "HEAD"])
async def serve_font(font_name: str):
    font_file = os.path.abspath(os.path.join(FONTS_DIR, font_name))
    if font_file.startswith(FONTS_DIR) and os.path.isfile(font_file):
        media_type = "font/ttf"
        if font_name.endswith(".woff2"):
            media_type = "font/woff2"
        elif font_name.endswith(".woff"):
            media_type = "font/woff"
        return FileResponse(
            font_file,
            media_type=media_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Font {font_name} not found")


@app.get("/api/health")
@app.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """Fast health check: returns ok and flags without external API calls."""
    if os.environ.get("TEST_MODE") == "true" and not request.query_params.get("verbose"):
        return {"status": "ok"}

    from backend.memory import _SEEDED_PAGES_CACHE
    gemini_key = bool((os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip())
    groq_key = bool(os.environ.get("GROQ_API_KEY", "").strip())
    tts_key = bool((os.environ.get("TTS_API_KEY") or os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip())
    memory_loaded = bool(_SEEDED_PAGES_CACHE is not None and len(_SEEDED_PAGES_CACHE) > 0)
    gemini_disabled = os.environ.get("TTS_DISABLE_GEMINI", "false").lower() in ("true", "1", "yes")
    groq_disabled = os.environ.get("TTS_DISABLE_GROQ", "false").lower() in ("true", "1", "yes")

    return {
        "status": "ok",
        "keys": {
            "gemini": gemini_key,
            "groq": groq_key,
            "tts_gemini": tts_key,
        },
        "memory_index_loaded": memory_loaded,
        "tts_disabled": {
            "gemini": gemini_disabled,
            "groq": groq_disabled,
        },
    }


@app.get("/api/config")
@app.get("/config")
async def get_config() -> Dict[str, Any]:
    """Returns public client configuration (e.g. Google OAuth Client ID)."""
    return {
        "google_client_id": (os.environ.get("GOOGLE_CLIENT_ID") or "").strip(),
    }


# --- Authentication & Session Endpoints ---
@app.post("/api/auth/google", response_model=AuthResponse)
@app.post("/auth/google", response_model=AuthResponse)
async def auth_google(req: GoogleAuthRequest, response: Response):
    """
    Verifies a Google OAuth ID token, provisions/updates user account,
    and returns a persistent session token + secure session cookie.
    """
    try:
        id_info = verify_google_id_token(req.credential)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {exc}",
        )

    sub = id_info.get("sub")
    email = id_info.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account payload missing required sub or email",
        )

    name = req.name or id_info.get("name") or email.split("@")[0]
    picture = id_info.get("picture") or ""

    user, is_new = create_or_update_google_user(
        google_sub=sub,
        email=email,
        name=name,
        picture=picture,
        dob=req.dob or "",
        age=req.age,
    )

    token = create_session(user["id"])
    response.set_cookie(
        key="inkmentor_session",
        value=token,
        httponly=True,
        max_age=30 * 24 * 3600,
        samesite="lax",
    )
    return AuthResponse(token=token, user=UserResponse(**user), is_new=is_new)


@app.get("/api/auth/me", response_model=UserResponse)
@app.get("/auth/me", response_model=UserResponse)
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Protected endpoint: returns the authenticated user's profile."""
    return UserResponse(**user)


@app.post("/api/auth/profile", response_model=UserResponse)
@app.put("/api/auth/profile", response_model=UserResponse)
async def update_profile(
    req: ProfileUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Protected endpoint: updates learner profile details (name, DOB, age)."""
    updated = update_user_profile(user["id"], name=req.name, dob=req.dob, age=req.age)
    return UserResponse(**updated)


@app.post("/api/auth/logout")
@app.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(None),
):
    """Revokes the current session token from the database and clears cookies."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get("inkmentor_session")
    if token:
        delete_session(token)
    response.delete_cookie("inkmentor_session")
    return {"status": "logged_out"}



@app.get("/api/health/deep")
@app.get("/health/deep")
async def deep_health_check() -> Dict[str, Any]:
    """Optional deep health check: makes 1 minimal Gemini call to verify key and model connectivity."""
    enabled = os.environ.get("ENABLE_DEEP_HEALTH", "false").lower() in ("true", "1", "yes")
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deep health check is disabled. Set ENABLE_DEEP_HEALTH=true to enable.",
        )
    from backend.llm import call_llm
    import time
    t0 = time.time()
    try:
        resp = await asyncio.to_thread(call_llm, "ping", "Reply with pong", 0.0)
        dur_ms = round((time.time() - t0) * 1000.0, 1)
        return {
            "status": "ok",
            "gemini": "connected",
            "latency_ms": dur_ms,
            "model": os.environ.get("LLM_MODEL", "gemini-3-flash-preview"),
        }
    except Exception as exc:
        err_msg = str(exc)
        key = os.environ.get("LLM_API_KEY", "").strip()
        if key and key in err_msg:
            err_msg = err_msg.replace(key, "[REDACTED]")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Deep health verification failed: {err_msg}",
        )


logger = logging.getLogger("inkmentor.api")


@app.post("/api/solve", response_model=SolveResponse)
@app.post("/solve", response_model=SolveResponse)
async def solve_endpoint(request: SolveRequest, req: Request, res: Response) -> SolveResponse:
    trace_id = req.headers.get("x-trace-id", "")
    if trace_id:
        res.headers["X-Trace-Id"] = trace_id
    try:
        response = await asyncio.to_thread(solve_problem, request)
        t = response.timing or {}
        res.headers["Server-Timing"] = (
            f"decode;dur={t.get('decode_ms', 0):.1f}, "
            f"llm;dur={t.get('llm_ms', 0):.1f}, "
            f"sympy;dur={t.get('sympy_ms', 0):.1f}, "
            f"total;dur={t.get('total_ms', 0):.1f}"
        )
        q_short = request.question[:30] + ("..." if len(request.question) > 30 else "")
        trace_str = f" trace={trace_id}" if trace_id else ""
        logger.info(
            f"[TIMING] /api/solve q='{q_short}'{trace_str} | total={t.get('total_ms', 0):.1f}ms | "
            f"decode={t.get('decode_ms', 0):.1f}ms | "
            f"llm={t.get('llm_ms', 0):.1f}ms (in={t.get('input_tokens')}, out={t.get('output_tokens')}, think={t.get('thinking_tokens')}) | "
            f"sympy={t.get('sympy_ms', 0):.1f}ms (startup={t.get('sympy_startup_ms', 0):.1f}ms, calc={t.get('sympy_calc_ms', 0):.1f}ms) | "
            f"retries={t.get('retries', 0)}"
        )
        return response
    except RuntimeError as re:
        # LLM provider failures map to 502 Bad Gateway
        if "LLM provider call failed" in str(re) or "Missing required environment variable" in str(re):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM upstream error: {re}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred.",
        )
    except Exception as exc:
        # Prevent leaking sensitive traceback details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {type(exc).__name__}",
        )


@app.post("/api/recognize", response_model=RecognizeResponse, response_model_exclude_none=True)
@app.post("/recognize", response_model=RecognizeResponse, response_model_exclude_none=True)
async def recognize_endpoint(request: RecognizeRequest, req: Request, res: Response) -> RecognizeResponse:
    trace_id = req.headers.get("x-trace-id", "")
    if trace_id:
        res.headers["X-Trace-Id"] = trace_id
    try:
        response = await asyncio.to_thread(recognize_image, request)
        t = response.timing or {}
        res.headers["Server-Timing"] = (
            f"decode;dur={t.get('decode_ms', 0):.1f}, "
            f"llm;dur={t.get('llm_ms', 0):.1f}, "
            f"total;dur={t.get('total_ms', 0):.1f}"
        )
        trace_str = f" trace={trace_id}" if trace_id else ""
        logger.info(
            f"[TIMING] /api/recognize{trace_str} | total={t.get('total_ms', 0):.1f}ms | "
            f"decode={t.get('decode_ms', 0):.1f}ms | "
            f"llm={t.get('llm_ms', 0):.1f}ms (in={t.get('input_tokens')}, out={t.get('output_tokens')}, think={t.get('thinking_tokens')}) | "
            f"retries={t.get('retries', 0)}"
        )
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except RuntimeError as re:
        clean_msg = str(re)
        api_key = os.environ.get("LLM_API_KEY")
        if api_key and api_key in clean_msg:
            clean_msg = clean_msg.replace(api_key, "[REDACTED]")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Vision provider error: {clean_msg}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {type(exc).__name__}",
        )


@app.post("/api/retrieve", response_model=RetrieveResponse)
@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_endpoint(request: RetrieveRequest) -> RetrieveResponse:
    try:
        response = await asyncio.to_thread(
            retrieve_context,
            query=request.query,
            pages=request.pages,
            threshold=request.threshold,
            top_k=request.top_k,
        )
        return response
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except RuntimeError as re:
        clean_msg = str(re)
        api_key = os.environ.get("LLM_API_KEY")
        if api_key and api_key in clean_msg:
            clean_msg = clean_msg.replace(api_key, "[REDACTED]")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {clean_msg}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {type(exc).__name__}",
        )


@app.post("/api/tts")
@app.post("/tts")
async def tts_endpoint(request: TTSRequest, req: Request):
    client_ip = get_client_ip(req)
    try:
        wav_bytes = await asyncio.to_thread(
            generate_tts_wav,
            request.text,
            client_ip=client_ip,
            voice_override=request.voice,
            position=request.position,
            lang_override=request.lang,
        )
        provider = getattr(wav_bytes, "provider", "gemini")
        attempts = getattr(wav_bytes, "attempts", 1)
        dur_ms = getattr(wav_bytes, "duration_ms", 0)
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Type": "audio/wav",
                "Cache-Control": "public, max-age=86400",
                "X-TTS-Provider": str(provider),
                "X-TTS-Duration-Ms": str(dur_ms),
                "X-TTS-Attempts": str(attempts),
                "Server-Timing": f"tts;dur={dur_ms}",
            },
        )
    except TTSAllProvidersFailed as tapf:
        return Response(
            content=json.dumps({"fallback": "browser", "reason": tapf.reason}),
            status_code=503,
            media_type="application/json",
            headers={
                "X-TTS-Provider": "none",
                "X-TTS-Attempts": str(tapf.attempts),
                "Server-Timing": f"tts;dur={tapf.duration_ms}",
            },
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(pe),
        )
    except TimeoutError as te:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS provider error: {te}",
        )
    except RuntimeError as re:
        clean_msg = str(re)
        for secret_name in ("LLM_API_KEY", "TTS_API_KEY", "GROQ_API_KEY", "GNANI_API_KEY"):
            sec = (os.environ.get(secret_name) or "").strip()
            if sec and sec in clean_msg:
                clean_msg = clean_msg.replace(sec, "[REDACTED]")
        if not clean_msg.startswith("TTS provider error:"):
            clean_msg = f"TTS provider error: {clean_msg}"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=clean_msg,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {type(exc).__name__}",
        )


@app.get("/api/tts/status", response_model=TTSStatusResponse)
@app.get("/tts/status", response_model=TTSStatusResponse)
async def tts_status_endpoint() -> TTSStatusResponse:
    model, voice, rate, _ = get_tts_config()
    provider = (os.environ.get("TTS_PROVIDER") or "gnani").strip().lower()
    gnani_key = os.environ.get("GNANI_API_KEY", "").strip()
    llm_key = (os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    active_provider = provider
    if provider == "gnani" and gnani_key:
        configured = True
    elif provider == "groq" and groq_key:
        configured = True
    elif provider == "gemini" and llm_key:
        configured = True
    else:
        # Fallback to whichever provider key is present
        configured = bool(gnani_key or llm_key or groq_key)
        if gnani_key:
            active_provider = "gnani"
        elif llm_key:
            active_provider = "gemini"
        elif groq_key:
            active_provider = "groq"

    return TTSStatusResponse(
        configured=configured,
        provider=active_provider if configured else None,
        model=model if configured else None,
        voice=voice if configured else None,
        language=os.environ.get("GNANI_TTS_LANG", "en-IN"),
        rate_per_min=rate,
    )


@app.post("/api/stt", response_model=STTResponse)
@app.post("/stt", response_model=STTResponse)
async def stt_endpoint(request: Request) -> STTResponse:
    """Transcribes user speech into math problem text using Gnani.ai Prisma STT.
    Accepts JSON with audio_base64 or raw audio bytes in request body.
    Supports indic-auto detection and code-mixed speech (e.g. Hinglish).
    """
    content_type = request.headers.get("content-type", "")
    audio_bytes: bytes = b""
    language = "indic-auto"

    if "application/json" in content_type:
        try:
            body_json = await request.json()
            req_obj = STTRequest(**body_json)
            if req_obj.language:
                language = req_obj.language
            if req_obj.audio_base64:
                import base64
                b64_str = req_obj.audio_base64
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                audio_bytes = base64.b64decode(b64_str)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid STT JSON payload: {exc}",
            )
    else:
        # Direct raw audio bytes (e.g. audio/webm, audio/wav, application/octet-stream)
        audio_bytes = await request.body()
        if request.query_params.get("language"):
            language = request.query_params.get("language", "indic-auto")

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No audio data provided in request",
        )

    try:
        transcript = await asyncio.to_thread(
            transcribe_speech_gnani,
            audio_bytes,
            language_code=language,
        )
        return STTResponse(
            transcript=transcript,
            language=language,
            model=os.environ.get("GNANI_STT_MODEL", "prisma-v3.0"),
            provider="gnani",
        )
    except RuntimeError as re:
        clean_msg = str(re)
        gnani_key = os.environ.get("GNANI_API_KEY", "").strip()
        if gnani_key and gnani_key in clean_msg:
            clean_msg = clean_msg.replace(gnani_key, "[REDACTED]")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=clean_msg,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"STT processing error: {type(exc).__name__}",
        )


@app.get("/{file_name:path}")
async def serve_static_fallback(file_name: str):
    """Local development static asset fallback route (CDN handles this in Vercel production)."""
    if file_name.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    target = os.path.abspath(os.path.join(PUBLIC_DIR, file_name))
    if not os.path.isfile(target):
        root_target = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", file_name))
        if os.path.isfile(root_target):
            target = root_target
    if os.path.isfile(target):
        media_type = "application/json" if file_name.endswith(".json") else "text/plain"
        return FileResponse(target, media_type=media_type)
    raise HTTPException(status_code=404, detail=f"File {file_name} not found")




