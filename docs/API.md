# InkMentor API Reference

This document provides the complete API reference for the InkMentor FastAPI backend. All endpoints adhere to strict JSON schemas validated via Pydantic models with automated test coverage across `backend/tests/`.

---

## Table of Endpoints

- [`GET /api/health`](#get-apihealth) — Health probe & serverless diagnostics
- [`POST /api/recognize`](#post-apirecognize) — Multimodal handwriting OCR
- [`POST /api/retrieve`](#post-apiretrieve) — Episodic notebook memory search
- [`POST /api/solve`](#post-apisolve) — CAS-verified mathematical step derivation
- [`POST /api/tts`](#post-apitts) — Real-time speech synthesis stream

---

### `GET /api/health`

Health check and serverless warm-up probe. Returns status flags, active LLM provider keys, and lazy-loaded memory status.

#### Request
```http
GET /api/health?verbose=true HTTP/1.1
Host: 127.0.0.1:8000
```

#### Response (`200 OK`)
```json
{
  "status": "ok",
  "keys": {
    "gemini": true,
    "groq": true,
    "tts_gemini": true
  },
  "memory_index_loaded": true,
  "tts_disabled": {
    "gemini": false,
    "groq": false
  }
}
```

---

### `POST /api/recognize`

Transcribes handwritten canvas crops into normalized math text and LaTeX using multimodal Gemini Vision.

#### Request
- **Headers:** `Content-Type: application/json`
- **Body:**
```json
{
  "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "media_type": "image/png"
}
```

#### Field Specifications:
- `image_base64` *(string, required)*: Base64-encoded image string with optional `data:image/png;base64,` prefix. Verified against PNG magic bytes (`89 50 4E 47 0D 0A 1A 0A`) and 4MB size ceiling.
- `media_type` *(string, required)*: Allowed values: `"image/png"`, `"image/jpeg"`.

#### Response (`200 OK`)
```json
{
  "readable": true,
  "latex": "y = \\sin(3x^2)",
  "question_text": "Differentiate y = sin(3x^2)",
  "needs_confirmation": true,
  "note": "",
  "timing": {
    "decode_ms": 1.2,
    "vision_ms": 612.4,
    "total_ms": 614.1
  }
}
```

---

### `POST /api/retrieve`

Performs high-dimensional cosine semantic retrieval over the notebook's indexed pages (3072-dimensional Gemini embeddings).

#### Request
- **Headers:** `Content-Type: application/json`
- **Body:**
```json
{
  "query": "Find the tangent plane to z = x^2 y at (2, 1)",
  "threshold": 0.65,
  "top_k": 2
}
```

#### Field Specifications:
- `query` *(string, required, 1-500 chars)*: Natural language question or LaTeX expression to embed and match.
- `threshold` *(float, default: 0.65, range: [0.0, 1.0])*: Minimum cosine similarity threshold.
- `top_k` *(int, default: 3, range: [1, 10])*: Maximum number of top matches to return.
- `pages` *(array of objects, optional)*: Client-supplied dynamic pages if overriding canonical prebuilt notes.

#### Response (`200 OK`)
```json
{
  "matches": [
    {
      "page": 3,
      "title": "Partial Derivatives & Tangent Planes",
      "snippet": "z - z0 = fx(x0, y0)(x - x0) + fy(x0, y0)(y - y0); normal vector n = <-fx, -fy, 1>",
      "similarity": 0.7410
    }
  ],
  "top_match": {
    "page": 3,
    "title": "Partial Derivatives & Tangent Planes",
    "snippet": "z - z0 = fx(x0, y0)(x - x0) + fy(x0, y0)(y - y0); normal vector n = <-fx, -fy, 1>",
    "similarity": 0.7410
  }
}
```

---

### `POST /api/solve`

Solves a mathematical problem, verifies every candidate transformation against an isolated SymPy CAS worker, and generates synchronized handwriting and narration steps.

#### Request
- **Headers:** `Content-Type: application/json`
- **Body:**
```json
{
  "question": "Differentiate y = sin(3x^2)",
  "context": [
    {
      "page": 3,
      "snippet": "Chain rule: d/dx f(g(x)) = f'(g(x)) * g'(x)"
    }
  ]
}
```

#### Response (`200 OK`)
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
      "write": "u = 3x^2, du/dx = 6x",
      "narration": "Let u equal three x squared, meaning its derivative is six x."
    },
    {
      "write": "dy/du = cos(u)",
      "narration": "Differentiating the outer sine function gives cosine of u."
    },
    {
      "write": "dy/dx = 6x cos(3x^2)",
      "narration": "Applying the chain rule gives six x cosine of three x squared."
    }
  ],
  "final_answer_latex": "6x\\cos(3x^2)",
  "final_answer_sympy": "6*x*cos(3*x**2)",
  "cites_pages": [3],
  "error": null,
  "timing": {
    "decode_ms": 0.4,
    "llm_ms": 820.5,
    "sympy_ms": 8.9,
    "total_ms": 831.2
  }
}
```

---

### `POST /api/tts`

Streams high-fidelity 24kHz mono PCM WAV speech with dynamic tutor vocal inflection ("Ink" persona).

#### Request
- **Headers:** `Content-Type: application/json`
- **Body:**
```json
{
  "text": "Applying the chain rule gives six x cosine of three x squared.",
  "position": "last",
  "voice": null
}
```

#### Field Specifications:
- `text` *(string, required, 1-300 chars)*: Natural spoken English sentence without mathematical notation symbols.
- `position` *(string, optional, default: `"middle"`)*: One of `"first"`, `"middle"`, or `"last"` to adjust conversational pitch and closure cadences.
- `voice` *(string, optional)*: Explicit voice model override.

#### Response (`200 OK`)
- **Content-Type:** `audio/wav`
- **Headers:** `Cache-Control: public, max-age=86400`
- **Payload:** Binary 24kHz mono RIFF/WAV audio stream.
