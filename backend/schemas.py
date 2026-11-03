from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

TaskType = Literal[
    "differentiate",
    "integrate",
    "solve",
    "simplify",
    "factor",
    "expand",
    "definite_integrate",
    "double_integrate",
    "triple_integrate",
    "jacobian",
]


class ContextPage(BaseModel):
    page: int
    snippet: str


class SolveRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    context: List[ContextPage] = Field(default_factory=list)


class Step(BaseModel):
    latex: Optional[str] = None
    write: str
    narration: str


class ProblemInterpretation(BaseModel):
    task_type: TaskType
    variable: str = "x"
    expression_sympy: str
    bounds: Optional[str] = None


class LLMOutput(BaseModel):
    task_type: TaskType
    variable: str = "x"
    expression_sympy: str
    steps: List[Step]
    final_answer_latex: str
    final_answer_sympy: str
    cites_pages: List[int] = Field(default_factory=list)
    bounds: Optional[str] = None


class SolveResponse(BaseModel):
    verified: bool
    attempts: int
    problem: Optional[ProblemInterpretation] = None
    steps: List[Step] = Field(default_factory=list)
    final_answer_latex: Optional[str] = None
    final_answer_sympy: Optional[str] = None
    cites_pages: List[int] = Field(default_factory=list)
    error: Optional[str] = None
    timing: Optional[Dict[str, Any]] = None


class RecognizeRequest(BaseModel):
    image_base64: str = Field(..., min_length=1, description="Base64 encoded image string, optional data: prefix")
    media_type: Literal["image/png", "image/jpeg"] = Field(..., description="MIME type: image/png or image/jpeg")


class RecognizeResponse(BaseModel):
    readable: bool
    latex: str
    question_text: str
    needs_confirmation: Literal[True] = True
    note: str = ""
    timing: Optional[Dict[str, Any]] = None


class RetrievePageItem(BaseModel):
    page: int
    title: str
    content: str


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    pages: Optional[List[RetrievePageItem]] = None
    threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    top_k: int = Field(default=3, ge=1, le=10)


class RetrievedPageMatch(BaseModel):
    page: int
    title: str
    snippet: str
    similarity: float


class RetrieveResponse(BaseModel):
    matches: List[RetrievedPageMatch]
    top_match: Optional[RetrievedPageMatch] = None


class TTSRequest(BaseModel):
    text: str = Field(..., description="Narration text to speak (1 to 300 characters)")
    voice: Optional[str] = Field(default=None, description="Optional TTS voice override")
    position: Optional[Literal["first", "middle", "last"]] = Field(
        default="middle",
        description="Position of the narration step: first, middle, or last"
    )
    lang: Optional[str] = Field(default=None, description="Optional language code override e.g. en-IN, hi-IN")


class TTSStatusResponse(BaseModel):
    configured: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    voice: Optional[str] = None
    language: Optional[str] = None
    rate_per_min: int = 40


# --- Speech-to-Text Schemas (Gnani Prisma) ---
class STTRequest(BaseModel):
    audio_base64: Optional[str] = Field(default=None, description="Base64-encoded audio bytes (WAV or WebM)")
    language: Optional[str] = Field(default="indic-auto", description="Language code (indic-auto, en-IN, hi-IN, etc.)")


class STTResponse(BaseModel):
    transcript: str = Field(..., description="Transcribed question/speech text")
    language: str = Field(default="indic-auto", description="Detected or requested language code")
    model: str = Field(default="prisma-v3.0", description="STT Model used")
    provider: str = Field(default="gnani", description="STT Provider used")


# --- Authentication Schemas ---
class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=1, description="Google OAuth ID Token JWT")
    name: Optional[str] = None
    dob: Optional[str] = None
    age: Optional[int] = None


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    dob: Optional[str] = Field(None, max_length=20)
    age: Optional[int] = Field(None, ge=0, le=150)


class UserResponse(BaseModel):
    id: int
    google_sub: str
    email: str
    name: str
    picture: Optional[str] = ""
    dob: Optional[str] = ""
    age: Optional[int] = None
    created_at: str
    last_login: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
    is_new: bool = False



