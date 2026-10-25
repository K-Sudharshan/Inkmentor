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

### 5. Text-To-Speech (TTS Narration)
```http
POST /api/tts
Content-Type: application/json
```
**Request:**
```json
{
  "text": "Let's use substitution with u equals 3x squared.",
  "position": "middle"
}
```
*Note: `text` must be 1 to 300 characters after trimming. Control characters are rejected with `422 Unprocessable Content`. `position` is optional (`"first"`, `"middle"`, or `"last"`, defaulting to `"middle"`).*

**Vocal Direction & Groq Orpheus Support:**
- Supported English voices: `autumn`, `diana`, `hannah`, `austin`, `daniel`, `troy`.
- Supported vocal directions: 1 to 2 lowercase words matching `^[a-z]+( [a-z]+)?$` (e.g. `cheerful`, `playfully`, `warmly`, `dramatically`, `professionally`).
- Direction routing per position:
  - `"first"`: uses `TTS_DIRECTION_FIRST` (falls back to `TTS_DIRECTION`)
  - `"middle"`: uses `TTS_DIRECTION`
  - `"last"`: uses `TTS_DIRECTION_LAST` (falls back to `TTS_DIRECTION`)
- Chunking: Groq Orpheus has a 200-character limit. If `[direction] text` exceeds 200 characters, the backend splits at sentence boundaries (or word boundaries), repeats the direction at the start of each chunk, and joins audio chunks into a single standard WAV using Python's `wave` module.
- Clean text guarantee: Bracketed directions are added only at the request to Groq server-side, never returned to the client or displayed on screen.

**Response (200 OK):**
- Binary audio data (`audio/wav`) encoded in 24kHz 16-bit mono PCM.
- Headers: `Content-Type: audio/wav`, `Cache-Control: public, max-age=86400`.

**Frontend Playback:**
- Audio is played with `TTS_PLAYBACK_RATE = 1.05` with `preservesPitch = true`. Writing animation duration is scaled by the playback rate to stay in sync with audio.

**Error Responses:**
- `422 Unprocessable Content`: Empty, whitespace-only, over-length (>300 chars), or contains invalid control characters.
- `429 Too Many Requests`: Client exceeds per-IP rate limit (`TTS_RATE_PER_MIN`, default 40/min).
- `502 Bad Gateway`: Upstream provider error, timeout (`TTS_TIMEOUT_SECONDS`, default 10s), or missing audio payload. API keys are redacted from error details.

---

### 6. TTS Status Check
```http
GET /api/tts/status
```
**Response (200 OK):**
```json
{
  "configured": true,
  "model": "gemini-3.8-flash-tts",
  "voice": "Puck",
  "rate_per_min": 40
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
# Run complete test suite (44 tests)
backend\.venv\Scripts\python -m pytest backend
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
14. **AI Solution Line Eraser & Undo/Clear Controls (Part B):** With the eraser tool active, dragging over an AI solution line removes that whole line (stroke-level feel matching student strokes). Hit-testing runs in page coordinates against rendered AI bounding boxes converted to canvas coordinates with an eraser radius tolerance (16px), keeping `pointer-events: none` on the AI text overlay. Erased lines are removed from the DOM and persisted in `pageAiOutput[cur]`. Erasing during active narration/solving cleanly cancels active speech synthesis, step timers, and animation frames, advancing the solve sequence ID so the pipeline terminates cleanly without voice cutoffs or console errors. The Page 1 callback link (`#mk`) is tied to the final step; erasing that step removes the callback link. Erasing the question header removes the question text and spacer while preserving subsequent steps. Undo (`#undo`) restores erased AI steps (via `type: 'ai-erase'` entries) and callbacks in their original positions. A header "Clear solution" button (`#clear-sol-btn`) confirms with the student, clears the solution, and supports undo restoration. Student ink erasure is unchanged.
15. **Centerline-Guided Pen Writing Animation for Handwriting Font (Part A):** True pen-stroke handwriting animation for the Reenie Beanie font outline. Centerline polylines are generated by the build tool `tools/extract_centerlines.py` from `tools/ReenieBeanie.ttf` (SIL Open Font License 1.1, verified in `tools/OFL.txt`). The extraction uses `skimage.morphology.skeletonize` with iterative spur pruning, micro-cycle breaking, collinear junction merging (for crossing strokes in `x` and `+`), top-to-bottom direction normalization, and natural handwriting stroke ordering (e.g. `i` stem then dot; `x` main diagonal then cross diagonal; `s` top-to-bottom single stroke; `2` single continuous stroke; `3` single stroke). The output is stored in `reenie_centerlines.json` and inlined for zero-dependency runtime execution. A feature flag `WRITE_ANIM = "pen"` (or `"reveal"`) is placed at the top of `InkMentor.html` to toggle between centerline pen animation and the legacy clip-path reveal. Solution lines render in genuine Reenie Beanie font outline with gradient ink (`url(#ai-ink-grad)`), masked by the centerline polylines scaled to character size. Strokes animate sequentially using `stroke-dashoffset` in proportion to stroke length with subtle pen-lift pauses between characters, while an amber glowing pen-tip dot (`.pen-tip`) traces the active stroke head via `getPointAtLength`. Raised exponents scale by 60% with upward shift, inline math symbols (`int`, `sqrt`, `pi`) animate in sequential order, and unextracted characters fall back to per-glyph diagonal reveals without dropping content. `prefers-reduced-motion` and `duration <= 0` render instantly without animation.
16. **Self-Hosted Caveat Handwriting Font & Retuned Typography Metrics:** The AI handwriting font is switched to Caveat Regular (`fonts/Caveat-Regular.ttf`, unitsPerEm 1000, SIL Open Font License), self-hosted relative to the served page with `@font-face` (`font-display: swap`) and fallback stack `("Caveat", "Reenie Beanie", cursive)`. Static font delivery is handled via `/fonts/{font_name}` with `media_type="font/ttf"` resolved relative to `backend/main.py`. Font loading is strictly gated by `ensureFontLoaded()` awaiting `document.fonts.load('46px "Caveat"')` and `document.fonts.ready` prior to any text measurements, solution animations, or eraser hit testing to prevent layout jumps or unstyled layout measurements. The font choice is switchable via top-level constant `AI_FONT = "caveat"` (or `"reenie"`). In compliance with Rule 6, centerline-mask writing mode is disabled for Caveat (since Reenie-derived centerlines do not match Caveat glyph contours) and replaced by the pen-style reveal paired with the glowing amber-to-coral pen-tip dot (`.ai-pen-tip-dot`). Typography metrics are retuned for Caveat's bolder, taller glyphs: font size `calc(var(--g) * 1.45)` (46.4px, yielding an x-height of ~16px matching half of a 32px grid square), line-height `calc(var(--g) * 1.65)` (52.8px), raised exponents (`EXPONENT_SCALE = 0.58`, `EXPONENT_SHIFT = '0.44em'`, `EXPONENT_RIGHT_GAP = '0.16em'`), inline math symbols (`INTEGRAL_SCALE = 1.50`, `INTEGRAL_STROKE_WIDTH = 3.2`, `INTEGRAL_VERTICAL_ALIGN = '-0.30em'`, `SQRT_STROKE_WIDTH = 3.0`, `PI_STROKE_WIDTH = 3.0`), ink glow tightened to `drop-shadow(0 0 3.5px rgba(255, 94, 126, 0.28))` to prevent muddiness on bolder stems, delimiter constraint for `/`, `(`, `)` (`.math-delim` at `0.94em`), and pen-tip dot sized to 8px. Reenie Beanie metrics and centerline mode remain fully preserved when `AI_FONT = "reenie"`.
17. **Sequential Line-by-Line Writing Animation & Instant Render Separation:** Live solves from `POST /api/solve` strictly follow an animated path while reloads, page navigation, undos, and layout resizes execute an instant path (`render({ animate: false })`). In the animated path, DOM elements for step $i+1$ are never inserted into `#notes` until step $i$ has completely finished both its pen drawing and voice narration (`Promise.all`), preventing any flash of finished future text. When step $i$ is created, its closed clip-path (`inset(-16px 100% -16px 0)`) is applied synchronously prior to DOM insertion. The glowing pen-tip dot appears at the start of line $i$, moves synchronously left-to-right with speech pacing, and hides at line completion before a brief 400ms pause precedes step $i+1$. The question header is displayed immediately as static problem prompt context, while the Page 1 callback link (`#mk`) appears only after all solution steps are finished. Interruption (switching pages, erasing, or solving again) cancels speech and animation frames cleanly without console errors or half-hidden lines.
18. **Solve-In-Progress Guard, Pixel-Level Isolation, Duplicate Line Prevention & Vinculum Radical (Parts A, B, C):**
    - **Part A (Zero Premature Ink Pixels):** Root cause identified: `ensureFontLoaded().then(render)` and background resize handlers fired asynchronously during live solves after `pageAiOutput[cur]` had already been populated, causing `render()` to synchronously wipe `#notes` and reveal all steps at 0ms. Fixed by introducing an explicit `solveInProgressSeqId` and `solveInProgressPage` guard. Re-render requests matching the active solve sequence and page are ignored, preserving zero-pixel isolation in all future step slots. Verified with automated 100ms CDP frame captures (`tools/test_pixel_writing_suite.py`) confirming zero ink pixels in all future line slots across entire solve pipelines, with interactive screencast player in `tools/out/screencast.html`.
    - **Part B (Duplicate Line Prevention):** Updated solver prompt rule in `backend/prompts.py` requiring the final step to express the result as a new line that does not repeat the previous line. Added validator check in `backend/solver.py` (`validate_llm_steps`) rejecting consecutive identical `write` strings to trigger automatic retry. Verified with unit tests with mocked LLM output (`test_15` and `test_16`, 34 total pytest tests passing).
    - **Part C (Square Root Symbol with Vinculum):** Fixed inline SVG square root radical in `createSvgSymbol('sqrt')` to draw a small leading tick, downward stroke, rising stroke, and extending horizontal vinculum bar (`M 1 20 L 4 23 L 9 34 L 16 5 L {w-2} 5`) with stroke weight matching Caveat (2.8px, round cap/join). Formatter parses nested parentheses (`sqrt(3)`, `sqrt(x^2 + 1)`), measures argument text bounding boxes, and extends the vinculum precisely over the radicand.
19. **Server-Side Gemini Text-To-Speech & Automatic Browser Voice Fallback:** Replaced the flat browser speech with warm, natural tutor voice narration ("Ink") generated server-side using Gemini TTS (`gemini-3.8-flash-tts`, default voice `Puck`, 24kHz 16-bit mono WAV). In-memory LRU cache (200 entries, single-worker assumption) avoids repeat calls and redundant latency. While step $i$ writes and narrates, step $i+1$ audio is prefetched in the background (at most one ahead). First-step audio is requested together with the solve result, with a 4-second timeout showing "Getting ready..." before transparently falling back to browser voice. Any TTS failure (rate limit 429, timeout, 502, network failure, or blocked autoplay) falls back to browser `speechSynthesis` automatically for that step with zero disruption or intrusive error messages to the student. Barge-in (switching pages, erasing lines, new solve, or clear solution) immediately stops the audio element, aborts in-flight network requests (`AbortController`), and cancels speech synthesis. The engine is switchable via `TTS_MODE = 'cloud' | 'browser'` at the top of `InkMentor.html`.
20. **End-to-End Latency Optimizations (Verification-Preserved Performance Suite):**
    A systematic optimization suite cutting solve-to-first-stroke latency without compromising SymPy verification (verified-before-shown remains strictly preserved; no unverified steps are streamed).
    - **Optimization A: Pre-Warmed SymPy Worker Pool (`USE_SYMPY_WORKER_POOL=true`):**
      Eliminated the Python startup + `import sympy` tax on every verification request by keeping a persistent, pre-warmed worker process loaded at server startup. Verification latency dropped from **788.2 ms median down to 8.9 ms (an 88x speedup)**. Hard 10s timeouts kill and immediately spawn fresh replacements without hanging or leaking state.
    - **Optimization B: Gemini Transport Reuse & Minimal Thinking Budget (`USE_OPTIMIZED_LLM_CONFIG=true`):**
      Re-uses `genai.Client` instances to avoid per-request HTTP transport socket re-negotiations. Applies `thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL)` and bounds `max_output_tokens=1024`, cutting Gemini 3.5 thinking overhead from >15s down to <1s.
    - **Optimization C: Output Pruning & Prompt Tightening:**
      Made `step.latex` optional in `Step` schema (`backend/schemas.py`) and removed it from `SYSTEM_PROMPT` (the UI strictly uses `step.write` for handwriting animations and `step.narration` for TTS). Tightened step constraints from 3-6 to 3-5 steps and narration length to 10-20 words, eliminating dead token generation and accelerating voice synthesis.
    - **Optimization D: Downscaled Vision Recognition Crop (`RECOGNIZE_MAX_SIDE=768`):**
      Downscaled offscreen canvas crops from 1024px to 768px max side in `InkMentor.html`, reducing image payload bytes by ~44% and accelerating Gemini vision OCR processing while preserving handwriting transcription accuracy.
    - **Optimization E: Immediate Batch TTS Prefetch with Concurrency 3 (`TTS_PREFETCH_CONCURRENCY=3`):**
      Prefetches all step narrations in parallel with a concurrency pool of 3 immediately upon `/api/solve` arrival instead of waiting for each step's animation to finish. Step 0 starts audio playback immediately; subsequent steps are cached in memory before previous steps finish animating, eliminating inter-step pauses.
    - **Optimization F: Speculative Solve on Confirm (`SPECULATIVE_SOLVE=true`):**
      When `/api/recognize` returns the transcribed question text, `/api/solve` is triggered in the background speculatively while the student reads the confirmation modal (~2-3s pause). When the student taps "Solve", the response is already in-flight or completed, dropping first-stroke latency to **near 0 ms**. Any edit or cancellation instantly aborts the speculative request via `AbortController`.
    - **Optimization G: Dynamic Stage Tracking & 3s Elapsed Timer:**
      Replaced the generic status spinner with real-time stage progress indicators ("Recognizing handwriting...", "Verifying with SymPy...", "Preparing Ink's voice..."). If any stage exceeds 3.0s, an live elapsed timer displays ("Verifying with SymPy... (3.4s)") so the student sees active server progress.
    - **Optimization H: Candidate Model Benchmark (Report):**
      Benchmarked active Gemini models across 5 calculus and algebra problems. While `gemini-3.5-flash-lite` provides 80% first-pass verification at 5.4s average pure latency, `gemini-3.5-flash` achieved 80% first-pass verification in only **2.78s average latency** (2x faster). Maintained `gemini-3.5-flash-lite` in production per specification, configurable via `LLM_MODEL`.

### Performance Measurement Summary

| Metric / Stage | Baseline (Before) | Post-Optimization (After) | Speedup / Impact |
| :--- | :--- | :--- | :--- |
| **SymPy Subprocess Verification** | 788.2 ms | **8.9 ms** | **88x faster** (-779.3 ms) |
| **SymPy Subprocess Startup** | 711.0 ms | **0.5 ms** | **1400x faster** (Pre-warmed) |
| **Prompt Token Overhead** | 1,665 tokens | **1,559 tokens** | **-106 tokens / req** |
| **Output Token Overhead** | 397 tokens | **291 tokens** | **-106 tokens / req** (no `step.latex`) |
| **Confirm-to-Stroke Latency** | ~7.8s – 45.7s | **~0.0s – 1.7s** | **Near Instant** (Speculative Solve) |
| **TTS Step Transitions** | 860 ms pause per step | **0 ms pause** | **Seamless** (Batch Concurrency 3) |
| **Recognition Image Payload** | 1024px max side | **768px max side** | **~44% smaller payload** |
| **Pytest Unit Test Suite** | 44/44 passing | **60/60 passing** | **100% contract compliance** |

21. **Vercel Hobby Serverless Deployment Architecture:**
    Adapted for zero-cost deployment on Vercel's Hobby (Free) tier as a single FastAPI serverless function paired with Edge static file delivery:
    - **Edge Static Delivery (`public/`):** Frontend `public/index.html`, handwriting fonts (`Caveat-Regular.ttf`), and centerline/glyph databases are served directly from Vercel's global CDN Edge with zero serverless compute cost and 0ms function cold start.
    - **Single Serverless Function (`api/index.py`):** Routes all `/api/*` requests via `vercel.json` rewrites to a lean FastAPI application.
    - **Read-Only Hardened Filesystem:** Relocates temporary audio disk caches strictly to `/tmp/inkmentor_audio_cache` via standard `tempfile.gettempdir()`, preventing crashes on read-only container filesystems.
    - **Lazy Initialization:** SymPy worker pools, seed embeddings, and API clients initialize on-demand with automatic fallback to isolated subprocesses with hard timeouts.
    - **Proxy Client IP Detection (`TRUST_PROXY_HEADERS=true`):** Respects Vercel's trusted `x-forwarded-for` and `x-real-ip` headers for sliding-window rate limiting.
    - **Provider Kill Switches (`TTS_DISABLE_GEMINI=true`, `TTS_DISABLE_GROQ=true`):** Bypasses exhausted providers with 0 network calls and 0 cost directly from the dashboard.
    - **Unobtrusive Serverless Wakeup Notice:** Automatically detects cold-start delays >3s on page load via `/api/health` and displays an amber status pill until warm.
    - **Local Development:** Run `python -m uvicorn api.index:app --port 8000 --reload` (or `backend.main:app`) to serve both the static frontend and API locally. See [DEPLOY.md](file:///c:/Users/durga/OneDrive/Desktop/inkmentor/DEPLOY.md) for full deployment instructions.


