# InkMentor

The notebook that writes back. A handwriting-first digital notebook for mathematics (algebra and calculus), featuring on-request AI reasoning with symbolic verification and notebook memory.

---

## API Endpoints

### 1. Health Check
```http
GET /api/health
```
**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### 2. Recognize Handwritten Math Problem
```http
POST /api/recognize
Content-Type: application/json
```
**Request:**
```json
{
  "image_base64": "<base64_string_with_optional_data_prefix>",
  "media_type": "image/png"
}
```
*Note: `media_type` must be either `"image/png"` or `"image/jpeg"`.*

**Successful Response (200 OK):**
```json
{
  "readable": true,
  "latex": "y = \\sin(3x^2)",
  "question_text": "Differentiate y = sin(3x^2)",
  "needs_confirmation": true,
  "note": ""
}
```

**Unreadable / Illegible Response (200 OK):**
```json
{
  "readable": false,
  "latex": "",
  "question_text": "",
  "needs_confirmation": true,
  "note": "Image appears blank or contains no legible math."
}
```

**Error Responses:**
- `422 Unprocessable Content`: Bad base64 string, unsupported media type (e.g. `image/gif`), empty image data, image exceeding `MAX_IMAGE_BYTES` (default 4MB), or mismatch between declared `media_type` and image magic bytes.
- `502 Bad Gateway`: Vision provider upstream error or invalid LLM response after 1 retry (max 2 LLM calls).

---

### 3. Solve & Verify Problem
```http
POST /api/solve
Content-Type: application/json
```
**Request:**
```json
{
  "question": "Differentiate y = sin(3x^2)",
  "context": [
    {
      "page": 1,
      "snippet": "chain rule: d/dx f(g(x)) = f'(g(x)) * g'(x)"
    }
  ]
}
```

**Response (200 OK):**
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

---

### 4. Retrieve Relevant Earlier Pages (Memory Index)
```http
POST /api/retrieve
Content-Type: application/json
```
**Request:**
```json
{
  "query": "Q3. Differentiate y = sin(3x^2)",
  "threshold": 0.65,
  "top_k": 3
}
```

**Response (200 OK):**
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

## Running the Server

```bash
# Activate virtual environment
backend\.venv\Scripts\activate

# Start server
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
The web interface is served at `http://127.0.0.1:8000/`.

---

## Running Tests

```bash
# Run complete test suite (32 tests)
backend\.venv\Scripts\pytest -v
```

---

## Assumptions

1. **Magic Byte Verification:** `POST /api/recognize` checks declared MIME types against standard magic bytes (`89 50 4E 47 0D 0A 1A 0A` for PNG and `FF D8 FF` for JPEG) to guard against corrupted or spoofed payloads.
2. **Payload Size Guard:** Maximum allowable decoded image size defaults to 4MB (`MAX_IMAGE_BYTES=4194304`), configurable via environment variable.
3. **Prompt Injection & Untrusted Data:** All image inputs to `/api/recognize` are treated as untrusted data; the vision prompt explicitly instructs the LLM to only transcribe and never execute any instruction-like text appearing in the image.
4. **Needs Confirmation:** `needs_confirmation` is set to `true` on all recognition responses so the student can verify or edit transcription before solving.
5. **SymPy Verification Boundary:** Symbolic verification evaluates the mathematical equivalence of the final computed answer against the interpreted problem, preventing hallucinated math from being written to the notebook.
6. **Per-Page State & AI Output Persistence:** New pages created via `+ New page` persist in `localStorage` under `inkmentor_notebook_pages_v1`. Solved questions and step answers persist per page under `inkmentor_notebook_ai_output_v1`. Seeded pages 1–7 provide study notes context, while newly created pages have no typed snippets and thus do not pollute `/api/solve` context.
7. **Circle Gesture Recognition:** A closed loop gesture is detected when the distance between the path start and end points is $\le \max(30\text{px}, 15\% \text{ path length})$ and the bounding box is $\ge 40\times 40\text{px}$. Student strokes having at least one point within the 12px padded bounding box are rendered onto a 1024px-max offscreen canvas and encoded as a PNG base64 payload.
8. **Confirmation & Fallback Interface:** If vision recognition succeeds, the student is presented with an editable text field prefilled with the recognized question. If the backend is down or recognition fails (`readable=false`), the modal opens with an informative error message and an empty input so the student can type the question manually without interruption.
9. **Handwritten Math Rendering & SVG Glyph Strategy:** The backend `/api/solve` contract and client-side persistence (`inkmentor_notebook_ai_output_v1` in `localStorage`) intentionally preserve raw ASCII notation (e.g. `int`, `sqrt(`, `pi`, `^`). Mathematical formatting occurs strictly at render time via `formatMathLine(raw)` returning DOM nodes. Because the notebook font ('Reenie Beanie') lacks natural handwriting glyphs for `∫` (U+222B), `√` (U+221A), and `π` (U+03C0)—falling back to rigid, typed system glyphs—these symbols are rendered as lightweight, inline SVG paths that adopt the exact AI ink gradient (`#FFA23A` to `#FF5E7E`) and pen stroke weight. Exponents (`^`) are converted to raised runs (`.math-sup`, 65% size, 0.45em baseline shift) while preserving parentheses for `sqrt(...)` and stripping them for `^(...)`.
10. **Pen-Stroke Writing Animation & Single-Line Hershey Font:** The CSS clip-path text reveal is replaced by a real pen-stroke writing animation. Font stroke data is sourced from the published npm package `hersheytext` (version `2.0.0`, MIT License, derived from Dr. A. V. Hershey's public domain US Naval Weapons Laboratory single-line engraving fonts). Single-stroke cursive glyphs are stored in `hershey_glyphs.json` and inlined for immediate access without CDN or network dependency. Each line is emitted as an SVG with progressive `stroke-dashoffset` path animations driven by `requestAnimationFrame`. A glowing amber pen-tip dot (`<circle class="pen-tip">`) glides at the head of the active stroke using `getPointAtLength()` and hides upon completion. Step durations dynamically match voice narration (`Math.max(2000, Math.min(8000, words * 400))` ms) to ensure long steps do not finish prematurely. Stored solutions on page navigation render instantly, `prefers-reduced-motion` is strictly respected, and page switching mid-animation cancels in-flight animation frames cleanly.
11. **Natural Voice Narration & Speech-Clock Sequencing:** Step counters like "Step 1 of 3" are removed from spoken text and prompt generation. Narration sentences are structured as short, natural tutor-like explanations (8 to 20 words). The Web Speech API acts as the clock: step $i+1$ begins strictly after step $i$'s utterance fires its `end` event AND drawing completes (`Promise.all`), preventing speech cut-offs. `speechSynthesis.cancel()` is never called between steps, only upon page switching or new solves. Stored solutions strip legacy step prefixes at speak-time without altering raw storage, and a 3-second safety margin timeout guarantees sequencing advances even if a browser drops speech events.
12. **Ink Persona & Light Voice Tuning:** The narrator speaks as "Ink", a warm, upbeat study buddy for students preparing for exams. Spoken narration employs natural spoken English and contractions ("let's", "that's"), varies openings across steps, weaves authentic math-tied motivation without hollow praise, and lands results warmly. Voice rate (`VOICE_RATE = 1.0`) and pitch (`VOICE_PITCH = 1.08`) constants are exposed at the top of the script for easy tuning, and the chosen voice name is logged once to the console for debugging. Narration lengths are bounded at 10–25 words with strict validator enforcement rejecting any narrations over 30 words.
13. **Restored Reenie Beanie Handwriting Font & Pen-Style Reveal Animation:** The solution lines are rendered using the project's cursive font ('Reenie Beanie') with the warm amber-to-coral AI gradient ink (`#FFA23A` to `#FF5E7E`) and subtle glow (`filter: drop-shadow(0 0 6px rgba(255, 94, 126, 0.40))`). The writing animation uses a pen-style reveal (progressive left-to-right clip-path reveal, not true centerline strokes) paired with an active pen-tip dot (`.ai-pen-tip-dot`) that glides smoothly across the reveal front with subtle handwriting bobbing and disappears when the line finishes. The single-line Hershey stroke font renderer and glyph database are fully preserved behind the toggle `USE_STROKE_FONT = false` at the top of `InkMentor.html` (defaulting to Reenie Beanie). Key typography and token spacing sizes are exposed as top-level constants (`AI_FONT_SIZE`, `INTEGRAL_SCALE = 1.55`, `INTEGRAL_STROKE_WIDTH = 2.4`, `INTEGRAL_VERTICAL_ALIGN = '-0.28em'`, `EXPONENT_SCALE = 0.60`, `EXPONENT_SHIFT = '0.38em'`, `EXPONENT_RIGHT_GAP = '0.14em'`, `INTEGRAL_LEFT_GAP = '0.06em'`, `INTEGRAL_RIGHT_GAP = '0.16em'`, `DIFFERENTIAL_GAP = '0.22em'`). Math expressions like `x^(3/2) / (3/2)` retain standard cursive font metrics for slashes and parentheses without oversized glyphs, exponents do not collide with adjacent characters, and unparseable input safely falls back to plain text.
