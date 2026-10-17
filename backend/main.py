import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.llm import validate_llm_env
from backend.memory import retrieve_context
from backend.recognize import recognize_image
from backend.schemas import (
    RecognizeRequest,
    RecognizeResponse,
    RetrieveRequest,
    RetrieveResponse,
    SolveRequest,
    SolveResponse,
)
from backend.solver import solve_problem

# Load .env file from backend directory if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify required environment variables on startup unless explicitly in test mode
    if os.environ.get("TEST_MODE") != "true":
        validate_llm_env()
    yield


app = FastAPI(title="InkMentor Math Solver API", version="1.0.0", lifespan=lifespan)

# CORS configuration
default_origins = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500"
allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", default_origins)
origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


HTML_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "InkMentor.html"))


@app.get("/")
async def serve_index():
    if os.path.exists(HTML_PATH):
        return FileResponse(HTML_PATH, media_type="text/html")
    return JSONResponse(
        status_code=404,
        content={"detail": "InkMentor.html not found"},
    )


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/solve", response_model=SolveResponse)
async def solve_endpoint(request: SolveRequest) -> SolveResponse:
    try:
        response = solve_problem(request)
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


@app.post("/api/recognize", response_model=RecognizeResponse)
async def recognize_endpoint(request: RecognizeRequest) -> RecognizeResponse:
    try:
        response = recognize_image(request)
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
async def retrieve_endpoint(request: RetrieveRequest) -> RetrieveResponse:
    try:
        response = retrieve_context(
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



