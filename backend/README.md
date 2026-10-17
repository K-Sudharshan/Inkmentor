# InkMentor Backend Service

FastAPI service for the InkMentor math reasoning and symbolic verification pipeline.

## 1. Setup & Installation

### Requirements
- Python 3.10+ (tested on Python 3.13.14 on Windows)
- Virtual environment

### Installation
```bash
# In the project root
python -m venv backend/.venv

# Activate on Windows
backend\.venv\Scripts\activate

# Install pinned dependencies
pip install -r backend/requirements.txt
```

---

## 2. Environment Variables

Create `backend/.env` (see `backend/.env.example`):

| Variable | Description | Example |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | LLM provider name (required, strictly validated) | `gemini` |
| `LLM_API_KEY` | Provider API authentication key (required) | `AIzaSy...` |
| `LLM_MODEL` | Exact model identifier to call (required, no hardcoded fallback) | `gemini-2.5-flash` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500` |

If `LLM_PROVIDER`, `LLM_API_KEY`, or `LLM_MODEL` is missing, the service fails fast on startup naming the missing variable. Keys are never logged or exposed in error messages.

---

## 3. Running the Server

```bash
# Run with uvicorn
backend\.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. API Contract & Curl Example

### Health Check
```bash
curl -i http://localhost:8000/api/health
```

### Solve & Verify Problem
```bash
curl -X POST http://localhost:8000/api/solve \
  -H "Content-Type: application/json" \
  -d '{"question":"Differentiate y = sin(3x^2)","context":[{"page":1,"snippet":"chain rule"}]}'
```

#### Successful Response (HTTP 200)
```json
{
  "verified": true,
  "attempts": 1,
  "problem": {
    "task_type": "differentiate",
    "variable": "x",
    "expression_sympy": "sin(3*x**2)"
  },
  "steps": [
    {
      "latex": "y = \\sin(3x^2)",
      "write": "y = sin(3x^2)",
      "narration": "We start with y equals sine of three x squared."
    },
    {
      "latex": "u = 3x^2 \\implies \\frac{du}{dx} = 6x",
      "write": "u = 3x^2, du/dx = 6x",
      "narration": "Let u equal three x squared so its derivative is six x."
    },
    {
      "latex": "\\frac{dy}{dx} = 6x \\cos(3x^2)",
      "write": "dy/dx = 6x cos(3x^2)",
      "narration": "Applying the chain rule gives six x cosine of three x squared."
    }
  ],
  "final_answer_latex": "6x\\cos(3x^2)",
  "final_answer_sympy": "6*x*cos(3*x**2)",
  "cites_pages": [1],
  "error": null
}
```

#### Unverified / Mismatch Response (HTTP 200)
If the solution fails verification after 1 retry:
```json
{
  "verified": false,
  "attempts": 2,
  "problem": {
    "task_type": "differentiate",
    "variable": "x",
    "expression_sympy": "sin(3*x**2)"
  },
  "steps": [],
  "final_answer_latex": null,
  "final_answer_sympy": null,
  "cites_pages": [],
  "error": "Derivative mismatch"
}
```

### Recognize Handwritten Math Problem
```bash
curl -X POST http://localhost:8000/api/recognize \
  -H "Content-Type: application/json" \
  -d '{"image_base64":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==","media_type":"image/png"}'
```

#### Successful Response (HTTP 200)
```json
{
  "readable": true,
  "latex": "y = \\sin(3x^2)",
  "question_text": "Differentiate y = sin(3x^2)",
  "needs_confirmation": true,
  "note": ""
}
```

#### Unreadable / Illegible Response (HTTP 200)
```json
{
  "readable": false,
  "latex": "",
  "question_text": "",
  "needs_confirmation": true,
  "note": "Image appears blank or contains no legible math."
}
```

#### Error Responses
- **HTTP 422 (Unprocessable Content):** Invalid base64, unsupported `media_type` (must be `image/png` or `image/jpeg`), empty image, payload exceeding `MAX_IMAGE_BYTES` (default 4MB), or declared `media_type` mismatch with file magic bytes.
- **HTTP 502 (Bad Gateway):** Vision LLM provider error or invalid JSON output after 1 retry (maximum 2 LLM calls).

---

### 4. Retrieve Relevant Earlier Pages (Memory Index)
```bash
curl -X POST http://localhost:8000/api/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"Q3. Differentiate y = sin(3x^2)","threshold":0.65,"top_k":3}'
```

#### Successful Response (HTTP 200)
```json
{
  "matches": [
    {
      "page": 1,
      "title": "Chain rule",
      "snippet": "Chain rule; d/dx f(g(x)) = f′(g(x)) · g′(x); e.g. d/dx (x²+1)³ = 6x(x²+1)²",
      "similarity": 0.7211
    },
    {
      "page": 4,
      "title": "Trig derivatives",
      "snippet": "Trig derivatives; d/dx sin x = cos x; d/dx cos x = −sin x",
      "similarity": 0.7078
    }
  ],
  "top_match": {
    "page": 1,
    "title": "Chain rule",
    "snippet": "Chain rule; d/dx f(g(x)) = f′(g(x)) · g′(x); e.g. d/dx (x²+1)³ = 6x(x²+1)²",
    "similarity": 0.7211
  }
}
```

---


## 5. Running Tests & Smoke Test

### Run Pytest Test Suite
```bash
backend\.venv\Scripts\python -m pytest -v backend/tests
```

### Run Live Smoke Test
```bash
backend\.venv\Scripts\python backend/scripts/smoke.py
```
*(If `LLM_API_KEY` is not present, `smoke.py` exits cleanly with a message without error.)*

---

## 6. Assumptions

1. **Subprocess Timeout on Windows:** `verify.py` invokes Python in a separate subprocess with `subprocess.run(..., timeout=10.0)` instead of `signal.alarm` or `multiprocessing.Process` to guarantee clean process termination without Windows pickling or spawn conflicts.
2. **Identifier Allowlist & Keyword Tokenization:** To prevent malicious code execution while supporting functions like `cos` and `cosh` (which contain the substring `os`), raw expressions are validated via regex tokenization against an explicit whitelist of math symbols, functions, and constants.
3. **Indefinite Integrals:** Constants of integration ($+ C$) are omitted from `final_answer_sympy`; verification differentiates the student/LLM answer to test whether `diff(ans, x) == expr`.
4. **Magic Byte Verification:** `POST /api/recognize` validates image payloads against declared MIME types using file header magic bytes (`89 50 4E 47 0D 0A 1A 0A` for PNG, `FF D8 FF` for JPEG) to prevent malicious or mismatched payloads.
5. **Prompt Injection & Untrusted Data:** `POST /api/recognize` treats all image content as untrusted user input; the vision prompt explicitly mandates transcribing only and forbids obeying any instruction-like text written in the image.


---

## 7. Known Limits

1. **Final Answer Verification Only:** SymPy verifies the mathematical correctness of the final result against the question's ground truth, but does not verify each intermediate step's algebraic equivalence.
2. **Question Translation Grounding:** If the LLM misinterprets the user's question into `expression_sympy`, verification verifies against the interpreted expression. The `problem` dictionary is returned so the frontend UI can explicitly show how the problem was understood.
