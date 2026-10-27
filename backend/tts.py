import hashlib
import io
import logging
import os
import re
import time
import wave
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import tempfile
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# Constants and Defaults
DEFAULT_TTS_MODEL = "gemini-3.8-flash-tts"
DEFAULT_TTS_VOICE = "Puck"
DEFAULT_RATE_LIMIT = 40
DEFAULT_TIMEOUT_SEC = 8.0
CACHE_CAPACITY = 200
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPWIDTH = 2  # 16-bit linear PCM

# Groq Orpheus Constants
GROQ_TTS_CHAR_LIMIT = 200
GROQ_SUPPORTED_VOICES = ("autumn", "diana", "hannah", "austin", "daniel", "troy")
DIRECTION_REGEX = re.compile(r"^[a-z]+( [a-z]+)?$")
_invalid_directions_warned: Set[str] = set()

# ponytail: In-memory LRU cache assuming single uvicorn worker process.
# Ceiling: 200 entries. Upgrade path for multi-worker deployment: shared Redis cache.
_tts_cache: OrderedDict[str, bytes] = OrderedDict()
_ip_rate_tracker: Dict[str, List[float]] = {}


def validate_direction(direction: Optional[str]) -> str:
    """Validates vocal direction: only 1 or 2 lowercase words (regex ^[a-z]+( [a-z]+)?$).
    Invalid directions are ignored and a warning is logged once."""
    if not direction:
        return ""
    dir_str = str(direction).strip()
    if not dir_str:
        return ""
    if not DIRECTION_REGEX.match(dir_str):
        if dir_str not in _invalid_directions_warned:
            _invalid_directions_warned.add(dir_str)
            logger.warning(
                f"Invalid TTS direction '{dir_str}' ignored (must be 1 or 2 lowercase words matching ^[a-z]+( [a-z]+)?$)"
            )
        return ""
    return dir_str


def get_direction_for_position(position: Optional[str] = "middle") -> str:
    """Selects and validates vocal direction based on step position ('first', 'middle', 'last').
    Fallback: TTS_DIRECTION_FIRST/LAST fall back to TTS_DIRECTION if unset."""
    pos = (position or "middle").strip().lower()
    mid_dir = os.environ.get("TTS_DIRECTION", "").strip()
    if pos == "first":
        raw_dir = os.environ.get("TTS_DIRECTION_FIRST", "").strip() or mid_dir
    elif pos == "last":
        raw_dir = os.environ.get("TTS_DIRECTION_LAST", "").strip() or mid_dir
    else:
        raw_dir = mid_dir
    return validate_direction(raw_dir)


def chunk_text_with_direction(text: str, direction: str = "", limit: int = GROQ_TTS_CHAR_LIMIT) -> List[str]:
    """Splits input text into chunks respecting the character limit (default 200).
    Repeats [direction] at the start of each chunk if a valid direction is provided.
    Splits at sentence boundaries first; falls back to word boundaries if a sentence exceeds the limit."""
    prefix = f"[{direction}] " if direction else ""
    max_chunk_text = limit - len(prefix)
    if max_chunk_text <= 0:
        raise ValueError("Direction prefix is too long for character limit")

    trimmed = text.strip()
    if not trimmed:
        return [prefix.strip()] if prefix else [""]

    if len(prefix) + len(trimmed) <= limit:
        return [f"{prefix}{trimmed}"]

    # Split at sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", trimmed)
    chunks: List[str] = []
    current_sentences: List[str] = []
    current_len = 0

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(s) > max_chunk_text:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_len = 0

            words = re.split(r"\s+", s)
            current_words: List[str] = []
            words_len = 0
            for w in words:
                if not w:
                    continue
                while len(w) > max_chunk_text:
                    if current_words:
                        chunks.append(" ".join(current_words))
                        current_words = []
                        words_len = 0
                    chunks.append(w[:max_chunk_text])
                    w = w[max_chunk_text:]

                needed = len(w) if not current_words else words_len + 1 + len(w)
                if needed <= max_chunk_text:
                    current_words.append(w)
                    words_len = needed
                else:
                    if current_words:
                        chunks.append(" ".join(current_words))
                    current_words = [w]
                    words_len = len(w)
            if current_words:
                chunks.append(" ".join(current_words))
        else:
            needed = len(s) if not current_sentences else current_len + 1 + len(s)
            if needed <= max_chunk_text:
                current_sentences.append(s)
                current_len = needed
            else:
                chunks.append(" ".join(current_sentences))
                current_sentences = [s]
                current_len = len(s)

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return [f"{prefix}{c}" for c in chunks]


def join_wav_bytes(wav_list: List[bytes]) -> bytes:
    """Concatenates multiple standard WAV byte streams into a single playable WAV stream.
    Verifies that all chunks share identical audio parameters (channels, sample width, framerate)."""
    if not wav_list:
        return b""
    if len(wav_list) == 1:
        return wav_list[0]

    with wave.open(io.BytesIO(wav_list[0]), "rb") as wf0:
        nchannels = wf0.getnchannels()
        sampwidth = wf0.getsampwidth()
        framerate = wf0.getframerate()
        frames = [wf0.readframes(wf0.getnframes())]

    for idx, w_bytes in enumerate(wav_list[1:], 1):
        with wave.open(io.BytesIO(w_bytes), "rb") as wf:
            p = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
            if p != (nchannels, sampwidth, framerate):
                raise ValueError(
                    f"WAV chunk {idx} audio parameters mismatch: expected "
                    f"{(nchannels, sampwidth, framerate)}, got {p}"
                )
            frames.append(wf.readframes(wf.getnframes()))

    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as out_wf:
        out_wf.setnchannels(nchannels)
        out_wf.setsampwidth(sampwidth)
        out_wf.setframerate(framerate)
        for f in frames:
            out_wf.writeframes(f)
    return out_buf.getvalue()


def get_tts_config() -> Tuple[str, str, int, float]:
    """Retrieves TTS settings from environment variables."""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)
    model = os.environ.get("LLM_TTS_MODEL", DEFAULT_TTS_MODEL).strip()
    voice = (os.environ.get("TTS_VOICE") or os.environ.get("GROQ_TTS_VOICE") or DEFAULT_TTS_VOICE).strip()
    try:
        rate = int(os.environ.get("TTS_RATE_PER_MIN", DEFAULT_RATE_LIMIT))
    except ValueError:
        rate = DEFAULT_RATE_LIMIT
    try:
        timeout = float(os.environ.get("TTS_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SEC))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SEC
    return model, voice, rate, timeout


def validate_tts_text(text: Optional[str]) -> str:
    """Validates narration text according to backend requirements:
    - 1 to 300 characters after trimming
    - No control characters (ord < 32 except \t\n\r, or 127 <= ord <= 159)
    """
    if text is None:
        raise ValueError("Text parameter is required")
    trimmed = str(text).strip()
    if not trimmed:
        raise ValueError("Text must not be empty")
    if len(trimmed) > 300:
        raise ValueError(f"Text length ({len(trimmed)}) exceeds maximum allowable 300 characters")

    # Check for control characters
    for ch in trimmed:
        code = ord(ch)
        if (code < 32 and ch not in ("\t", "\n", "\r")) or (127 <= code <= 159):
            raise ValueError("Text contains invalid control characters")

    return trimmed


def check_ip_rate_limit(client_ip: str, limit_per_min: int) -> bool:
    """Sliding-window per-IP rate limiter. Returns True if request is allowed."""
    now = time.time()
    cutoff = now - 60.0
    history = _ip_rate_tracker.get(client_ip, [])
    # Filter timestamps older than 60 seconds
    valid_history = [t for t in history if t > cutoff]
    if len(valid_history) >= limit_per_min:
        _ip_rate_tracker[client_ip] = valid_history
        return False
    valid_history.append(now)
    _ip_rate_tracker[client_ip] = valid_history
    return True


class AudioBytes(bytes):
    def __new__(cls, val: bytes, provider: str = "gemini", attempts: int = 1, duration_ms: int = 0):
        obj = super().__new__(cls, val)
        obj.provider = provider
        obj.attempts = attempts
        obj.duration_ms = duration_ms
        return obj


class TTSAllProvidersFailed(Exception):
    def __init__(self, reason: str = "ALL_PROVIDERS_FAILED", attempts: int = 0, duration_ms: int = 0):
        super().__init__(f"All TTS providers failed: {reason}")
        self.reason = reason
        self.attempts = attempts
        self.duration_ms = duration_ms


class TTSCircuitBreaker:
    def __init__(self):
        self.state: Dict[str, str] = {}  # "closed", "open", "half_open"
        self.consecutive_failures: Dict[str, int] = {}
        self.cooldown_until: Dict[str, float] = {}
        self.last_failure_reason: Dict[str, str] = {}

    def is_available(self, provider: str) -> bool:
        prov = provider.lower()
        st = self.state.get(prov, "closed")
        if st == "closed":
            return True
        now = time.time()
        cd = self.cooldown_until.get(prov, 0.0)
        if st == "open":
            if now >= cd:
                self.state[prov] = "half_open"
                logger.info(f"Circuit breaker for {prov} transitioned to half_open (probing)")
                return True
            return False
        if st == "half_open":
            return True
        return True

    def record_success(self, provider: str):
        prov = provider.lower()
        self.state[prov] = "closed"
        self.consecutive_failures[prov] = 0
        self.cooldown_until[prov] = 0.0
        self.last_failure_reason[prov] = ""

    def record_failure(self, provider: str, reason: str, is_quota: bool = False, retry_delay: float = 0.0):
        prov = provider.lower()
        fails = self.consecutive_failures.get(prov, 0) + 1
        self.consecutive_failures[prov] = fails
        self.last_failure_reason[prov] = reason
        now = time.time()
        if is_quota:
            default_cd = float(os.environ.get("TTS_CIRCUIT_COOLDOWN_SEC", "600"))
            cooldown = retry_delay if retry_delay > 0 else default_cd
            self.state[prov] = "open"
            self.cooldown_until[prov] = now + cooldown
            logger.warning(f"Circuit breaker for {prov} OPENED on quota exhaustion for {cooldown:.1f}s ({reason})")
        else:
            threshold = int(os.environ.get("TTS_CIRCUIT_FAIL_THRESHOLD", "2"))
            st = self.state.get(prov, "closed")
            if fails >= threshold or st == "half_open":
                cooldown = float(os.environ.get("TTS_CIRCUIT_FAIL_COOLDOWN_SEC", "60"))
                self.state[prov] = "open"
                self.cooldown_until[prov] = now + cooldown
                logger.warning(f"Circuit breaker for {prov} OPENED on repeated failures for {cooldown:.1f}s ({reason})")

    def reset(self):
        self.state.clear()
        self.consecutive_failures.clear()
        self.cooldown_until.clear()
        self.last_failure_reason.clear()


circuit_breaker = TTSCircuitBreaker()


def extract_pcm_from_wav(wav_bytes: bytes) -> Tuple[bytes, int, int, int]:
    """Extracts (pcm_data, sample_rate, channels, sampwidth) from any valid or chunked WAV bytes."""
    if len(wav_bytes) < 12 or not wav_bytes.startswith(b"RIFF") or wav_bytes[8:12] != b"WAVE":
        return wav_bytes, SAMPLE_RATE, CHANNELS, SAMPWIDTH

    offset = 12
    sample_rate = SAMPLE_RATE
    channels = CHANNELS
    sampwidth = SAMPWIDTH
    pcm_data = b""

    import struct
    while offset + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[offset:offset+4]
        chunk_len = struct.unpack("<I", wav_bytes[offset+4:offset+8])[0]
        offset += 8

        if chunk_id == b"fmt ":
            if offset + 16 <= len(wav_bytes):
                fmt_data = wav_bytes[offset:offset+chunk_len]
                audio_fmt, n_ch, s_rate, _, _, bits_per_samp = struct.unpack("<HHIIHH", fmt_data[:16])
                channels = n_ch
                sample_rate = s_rate
                sampwidth = bits_per_samp // 8
        elif chunk_id == b"data":
            if chunk_len == 0xffffffff or offset + chunk_len > len(wav_bytes):
                pcm_data = wav_bytes[offset:]
            else:
                pcm_data = wav_bytes[offset:offset+chunk_len]
            break

        if chunk_len == 0xffffffff:
            break
        offset += chunk_len + (chunk_len % 2)

    if not pcm_data and len(wav_bytes) > 44:
        pcm_data = wav_bytes[44:]

    return pcm_data, sample_rate, channels, sampwidth


def normalize_to_canonical_wav(raw_bytes: bytes, target_sample_rate: int = SAMPLE_RATE) -> bytes:
    """Normalizes any provider audio (raw PCM or streaming WAV with 0xffffffff chunks)
    into a canonical standard 44-byte WAV header."""
    if not raw_bytes:
        return b""
    pcm_data, s_rate, n_ch, samp_w = extract_pcm_from_wav(raw_bytes)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(n_ch)
        wf.setsampwidth(samp_w)
        wf.setframerate(s_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Converts 24kHz 16-bit mono Linear PCM bytes into standard playable WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPWIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def get_wav_duration(wav_bytes: bytes) -> float:
    """Extracts duration from standard WAV header, with fallback to byte calculation."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            framerate = wf.getframerate()
            if framerate > 0:
                return wf.getnframes() / float(framerate)
    except Exception:
        pass
    return max(0.0, (len(wav_bytes) - 44) / float(SAMPLE_RATE * CHANNELS * SAMPWIDTH))


AUDIO_CACHE_DIR = os.path.join(tempfile.gettempdir(), "inkmentor_audio_cache")
try:
    os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
except Exception:
    pass


def get_cache_key(model: str, voice: str, text: str, direction: str = "") -> str:
    h = hashlib.sha256()
    h.update(f"{model}:{voice}:{direction}:{text}".encode("utf-8"))
    return h.hexdigest()


def cache_get(key: str) -> Optional[bytes]:
    if key in _tts_cache:
        _tts_cache.move_to_end(key)
        return _tts_cache[key]
    disk_file = os.path.join(AUDIO_CACHE_DIR, f"{key}.wav")
    if os.path.isfile(disk_file):
        try:
            with open(disk_file, "rb") as f:
                data = f.read()
            if len(_tts_cache) >= CACHE_CAPACITY:
                _tts_cache.popitem(last=False)
            _tts_cache[key] = data
            return data
        except Exception:
            pass
    return None


def cache_set(key: str, val: bytes) -> None:
    if key in _tts_cache:
        _tts_cache.move_to_end(key)
    else:
        if len(_tts_cache) >= CACHE_CAPACITY:
            _tts_cache.popitem(last=False)
    _tts_cache[key] = val
    disk_file = os.path.join(AUDIO_CACHE_DIR, f"{key}.wav")
    try:
        with open(disk_file, "wb") as f:
            f.write(val)
    except Exception:
        pass


def clear_cache() -> None:
    _tts_cache.clear()
    _ip_rate_tracker.clear()
    circuit_breaker.reset()
    if os.path.exists(AUDIO_CACHE_DIR):
        for f in os.listdir(AUDIO_CACHE_DIR):
            if f.endswith(".wav"):
                try:
                    os.remove(os.path.join(AUDIO_CACHE_DIR, f))
                except Exception:
                    pass


FALLBACK_TTS_MODELS = ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts")


def _call_groq_speech_single(chunk: str, voice_name: str, timeout_sec: float) -> bytes:
    """Internal helper to call Groq /audio/speech for a single text chunk (<= 200 chars)."""
    import json
    import urllib.request
    import urllib.error

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing required environment variable: GROQ_API_KEY")

    groq_model = os.environ.get("GROQ_TTS_MODEL", "canopylabs/orpheus-v1-english").strip()

    if voice_name and voice_name.lower() in GROQ_SUPPORTED_VOICES:
        groq_voice = voice_name.lower()
    else:
        env_voice = (os.environ.get("TTS_VOICE") or os.environ.get("GROQ_TTS_VOICE") or "autumn").strip().lower()
        groq_voice = env_voice if env_voice in GROQ_SUPPORTED_VOICES else "autumn"

    payload = json.dumps({
        "model": groq_model,
        "voice": groq_voice,
        "input": chunk,
        "response_format": "wav"
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/speech",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "InkMentor-TTS/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.read()
    except urllib.error.HTTPError as he:
        body = he.read().decode("utf-8", errors="ignore")
        if api_key in body:
            body = body.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"Groq TTS HTTP {he.code}: {body}") from None
    except Exception as exc:
        err_str = str(exc)
        if api_key in err_str:
            err_str = err_str.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"Groq TTS error: {err_str}") from None


def synthesize_speech_groq(text: str, voice_name: str, timeout_sec: float, direction: str = "") -> bytes:
    """Ultra-low latency Groq Text-to-Speech call.
    Supports short vocal directions, chunks text if exceeding the 200-character limit,
    repeats direction on each chunk, and joins audio chunks into a valid canonical WAV."""
    valid_dir = validate_direction(direction)
    chunks = chunk_text_with_direction(text, direction=valid_dir, limit=GROQ_TTS_CHAR_LIMIT)

    wav_chunks: List[bytes] = []
    for chunk in chunks:
        chunk_wav = _call_groq_speech_single(chunk, voice_name, timeout_sec)
        # Normalize each chunk if needed
        wav_chunks.append(normalize_to_canonical_wav(chunk_wav))

    return join_wav_bytes(wav_chunks)


def extract_retry_delay(exc: Exception) -> float:
    try:
        details = getattr(exc, "details", None)
        if details:
            for item in details:
                if isinstance(item, dict) and "retryDelay" in item:
                    delay_str = str(item["retryDelay"]).rstrip("s")
                    return float(delay_str)
    except Exception:
        pass
    s = str(exc)
    m = re.search(r"retryDelay[:\'\"\s]+([0-9]+(?:\.[0-9]+)?)s?", s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return 0.0


def synthesize_speech_gemini(
    text: str,
    model_name: str,
    voice_name: str,
    timeout_sec: float
) -> bytes:
    api_key = (os.environ.get("TTS_API_KEY") or os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Missing required environment variable: LLM_API_KEY or TTS_API_KEY")

    from google import genai
    from google.genai import types

    gemini_voice = voice_name if voice_name in ("Puck", "Charon", "Kore", "Fenrir", "Aoede") else DEFAULT_TTS_VOICE
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=gemini_voice)
            )
        ),
    )

    models_to_try = [model_name]
    for fb in FALLBACK_TTS_MODELS:
        if fb not in models_to_try:
            models_to_try.append(fb)

    last_exc = None
    start_time = time.time()
    for current_model in models_to_try:
        elapsed = time.time() - start_time
        remaining_timeout = max(1.0, timeout_sec - elapsed)

        def _call():
            return client.models.generate_content(
                model=current_model,
                contents=text,
                config=config,
            )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call)
            try:
                response = future.result(timeout=remaining_timeout)
            except FutureTimeoutError:
                raise TimeoutError(f"TTS provider call timed out after {timeout_sec:.1f}s")
            except Exception as exc:
                last_exc = exc
                err_msg = str(exc)
                logger.warning(
                    f"Gemini model {current_model} call failed ({err_msg}). Trying next fallback model if available..."
                )
                continue

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            if getattr(part, "inline_data", None) and part.inline_data.data:
                return normalize_to_canonical_wav(part.inline_data.data)

    if last_exc:
        raise last_exc
    raise RuntimeError("Gemini TTS provider returned an empty response")


def synthesize_speech_chain(
    text: str,
    model_name: str,
    voice_name: str,
    timeout_sec: float,
    direction: str = "",
    position: str = "middle",
) -> AudioBytes:
    """Executes strict TTS provider chain: Gemini -> Groq -> fallback to browser.
    Enforces per-provider timeouts, total request budget, and circuit breaker."""
    order_env = os.environ.get("TTS_PROVIDER_ORDER", "").strip().lower()
    single_provider = os.environ.get("TTS_PROVIDER", "").strip().lower()
    if order_env:
        providers = [p.strip() for p in order_env.split(",") if p.strip()]
    elif single_provider in ("groq", "gemini"):
        other = "gemini" if single_provider == "groq" else "groq"
        providers = [single_provider, other]
    else:
        providers = ["gemini", "groq"]

    timeout_gemini = float(os.environ.get("TTS_TIMEOUT_GEMINI_MS", "5000")) / 1000.0
    timeout_groq = float(os.environ.get("TTS_TIMEOUT_GROQ_MS", "4000")) / 1000.0
    total_budget = float(os.environ.get("TTS_TOTAL_BUDGET_MS", "7000")) / 1000.0

    disable_gemini = os.environ.get("TTS_DISABLE_GEMINI", "false").lower() in ("true", "1", "yes")
    disable_groq = os.environ.get("TTS_DISABLE_GROQ", "false").lower() in ("true", "1", "yes")

    chain_start = time.time()
    attempts = 0
    last_reason = "NO_PROVIDERS"

    for prov in providers:
        now = time.time()
        elapsed = now - chain_start
        remaining_budget = total_budget - elapsed
        if remaining_budget <= 0.2:
            last_reason = "TOTAL_BUDGET_EXCEEDED"
            logger.warning(f"TTS chain total budget ({total_budget:.1f}s) exceeded before trying {prov}")
            break

        if prov == "gemini" and disable_gemini:
            logger.info("Skipping gemini TTS (TTS_DISABLE_GEMINI=true)")
            last_reason = "DISABLED_GEMINI"
            continue

        if prov == "groq" and disable_groq:
            logger.info("Skipping groq TTS (TTS_DISABLE_GROQ=true)")
            last_reason = "DISABLED_GROQ"
            continue

        if not circuit_breaker.is_available(prov):
            logger.info(f"Skipping {prov} TTS (circuit breaker open)")
            last_reason = f"CIRCUIT_OPEN_{prov.upper()}"
            continue

        attempts += 1
        t_call_start = time.time()
        if prov == "gemini":
            prov_timeout = min(timeout_gemini, remaining_budget)
            try:
                raw_wav = synthesize_speech_gemini(text, model_name, voice_name, prov_timeout)
                canon_wav = normalize_to_canonical_wav(raw_wav)
                circuit_breaker.record_success("gemini")
                dur_ms = int((time.time() - t_call_start) * 1000)
                return AudioBytes(canon_wav, provider="gemini", attempts=attempts, duration_ms=dur_ms)
            except Exception as exc:
                err_str = str(exc)
                is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()
                retry_d = extract_retry_delay(exc) if is_quota else 0.0
                circuit_breaker.record_failure("gemini", err_str, is_quota=is_quota, retry_delay=retry_d)
                last_reason = "QUOTA_EXHAUSTED_GEMINI" if is_quota else "ERROR_GEMINI"
                logger.warning(f"Gemini TTS failed ({last_reason}): {err_str}; proceeding to next provider")
        elif prov == "groq":
            prov_timeout = min(timeout_groq, remaining_budget)
            try:
                raw_wav = synthesize_speech_groq(text, voice_name, prov_timeout, direction=direction)
                canon_wav = normalize_to_canonical_wav(raw_wav)
                circuit_breaker.record_success("groq")
                dur_ms = int((time.time() - t_call_start) * 1000)
                return AudioBytes(canon_wav, provider="groq", attempts=attempts, duration_ms=dur_ms)
            except Exception as exc:
                err_str = str(exc)
                is_quota = "429" in err_str or "too many requests" in err_str.lower() or "quota" in err_str.lower()
                circuit_breaker.record_failure("groq", err_str, is_quota=is_quota)
                last_reason = "QUOTA_EXHAUSTED_GROQ" if is_quota else "ERROR_GROQ"
                logger.warning(f"Groq TTS failed ({last_reason}): {err_str}; proceeding to next provider")

    total_dur_ms = int((time.time() - chain_start) * 1000)
    raise TTSAllProvidersFailed(reason=last_reason, attempts=attempts, duration_ms=total_dur_ms)


def synthesize_speech_provider(text: str, model_name: str, voice_name: str, timeout_sec: float, direction: str = "") -> bytes:
    """Direct provider call to TTS chain. Returns standard playable WAV bytes."""
    return synthesize_speech_chain(text, model_name, voice_name, timeout_sec, direction=direction)


def generate_tts_wav(
    text: str,
    client_ip: str = "127.0.0.1",
    voice_override: Optional[str] = None,
    position: Optional[str] = "middle"
) -> bytes:
    """Full TTS pipeline:
    1. Validation
    2. Rate limiting check
    3. Position-based vocal direction resolution
    4. Cache lookup (keyed by model, voice, direction, text)
    5. Provider chain synthesis
    6. Cache storage
    7. Logging length and duration only (never full text)
    """
    valid_text = validate_tts_text(text)
    model, default_voice, rate_limit, timeout_sec = get_tts_config()
    voice = voice_override.strip() if voice_override and voice_override.strip() else default_voice
    direction = get_direction_for_position(position)

    # Rate limit check
    if not check_ip_rate_limit(client_ip, rate_limit):
        raise PermissionError(f"Rate limit exceeded ({rate_limit} requests/min). Please try again shortly.")

    cache_key = get_cache_key(model, voice, valid_text, direction)
    cached_audio = cache_get(cache_key)
    if cached_audio:
        duration = get_wav_duration(cached_audio)
        logger.info(f"TTS Cache HIT: text_len={len(valid_text)}, dir='{direction}', dur={duration:.2f}s")
        return AudioBytes(cached_audio, provider="cache", attempts=0, duration_ms=int(duration * 1000))

    # Call provider chain (or patched synthesize_speech_provider)
    wav_bytes = synthesize_speech_provider(valid_text, model, voice, timeout_sec, direction=direction)
    canon_bytes = normalize_to_canonical_wav(wav_bytes)
    cache_set(cache_key, canon_bytes)

    duration = get_wav_duration(canon_bytes)
    prov = getattr(wav_bytes, "provider", "gemini")
    attempts = getattr(wav_bytes, "attempts", 1)
    dur_ms = getattr(wav_bytes, "duration_ms", int(duration * 1000))

    logger.info(
        f"TTS Provider Generated ({prov}): text_len={len(valid_text)}, dir='{direction}', dur={duration:.2f}s, size={len(canon_bytes)}B"
    )
    return AudioBytes(canon_bytes, provider=prov, attempts=attempts, duration_ms=dur_ms)

