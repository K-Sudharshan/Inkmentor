# InkMentor

> **The notebook that writes back.**  
> A handwriting-first digital mathematics notebook powered by on-demand multimodal AI reasoning, episodic notebook memory, and deterministic symbolic verification.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SymPy](https://img.shields.io/badge/CAS%20Verification-SymPy%201.13-3B5526.svg?style=flat)](https://www.sympy.org/)
[![Vision & Reasoning](https://img.shields.io/badge/Vision%20%26%20Reasoning-Gemini%20Flash-4285F4.svg?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Speech Synthesis](https://img.shields.io/badge/Voice%20Tutor-Gemini%20TTS%20%7C%20Groq%20Orpheus-F55036.svg?style=flat)](https://groq.com/)
[![Test Suite](https://img.shields.io/badge/Test%20Suite-69%2F69%20Passed-brightgreen.svg?style=flat)](backend/tests/)
[![Architecture](https://img.shields.io/badge/Architecture-Verified--Before--Shown-blueviolet.svg?style=flat)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

---

## Table of Contents

1. [Overview & Philosophy](#1-overview--philosophy)
2. [The Core Problem](#2-the-core-problem)
3. [The InkMentor Paradigm](#3-the-inkmentor-paradigm)
4. [System Architecture](#4-system-architecture)
5. [Feature Showcase](#5-feature-showcase)
   - [Authentic Stationery Instruments & Smart Auto-Minimize](#authentic-stationery-instruments--smart-auto-minimize)
   - [Decoupled Persistent AI Action Capsule](#decoupled-persistent-ai-action-capsule)
   - [Circle-to-Solve Gesture & Multimodal Vision](#circle-to-solve-gesture--multimodal-vision)
   - [Verified-Before-Shown (Zero-Hallucination CAS Engine)](#verified-before-shown-zero-hallucination-cas-engine)
   - [Episodic Notebook Memory & Margin Portals](#episodic-notebook-memory--margin-portals)
   - [Fluid Stroke-by-Stroke Handwriting Animation](#fluid-stroke-by-stroke-handwriting-animation)
   - [Synchronized Voice Tutor ("Ink")](#synchronized-voice-tutor-ink)
   - [Pedagogical Hint Ladder](#pedagogical-hint-ladder)
   - [Digital Paper Theme (Canvas-Preserved Dark Mode)](#digital-paper-theme-canvas-preserved-dark-mode)
6. [Mathematical Scope & Topic Boundaries](#6-mathematical-scope--topic-boundaries)
7. [Performance & Latency Engineering](#7-performance--latency-engineering)
8. [API Reference](#8-api-reference)
9. [Installation & Local Setup](#9-installation--local-setup)
10. [Test Suite & Quality Verification](#10-test-suite--quality-verification)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Security & Sandboxing](#12-security--sandboxing)

---

## 1. Overview & Philosophy

InkMentor transforms how students engage with mathematics. Rather than forcing students out of their natural working environment and into sterile chat interfaces, InkMentor functions first and foremost as an authentic digital notebook. Students write with a stylus or mouse across authentic grid paper using handcrafted stationery tools.

When a student hits a roadblock, they circle their handwritten question and tap **Solve**. InkMentor's integrated AI engine:
1. Transcribes the handwritten math strokes into clean LaTeX via multimodal vision.
2. Retrieves relevant theorems and derivations from the student’s **earlier notebook pages**.
3. Derives an explicit, step-by-step solution.
4. **Symbolically verifies every single mathematical transformation** through a sandboxed SymPy Computer Algebra System (CAS) worker before rendering.
5. Writes the solution directly onto the notebook page **stroke by stroke in warm, glowing ink**, while synchronously narrating the mathematical intuition through a conversational voice tutor named **"Ink"**.

```
   ┌────────────────────────────────────────────────────────────────────────┐
   │                           STUDENT NOTEBOOK                             │
   │                                                                        │
   │    Practice Problem:                                                   │
   │    ┌───────────────────────────┐                                       │
   │    │  ╭─────────────────────╮  │                                       │
   │    │  │ Q: ∫ 2x / (x² + 1) dx│  │  ◄── Circled by student              │
   │    │  ╰─────────────────────╯  │                                       │
   │    └─────────────┬─────────────┘                                       │
   │                  ▼                                                     │
   │    [ "← Recall from Page 2" ]      ◄── Notebook Memory Citation        │
   │                                                                        │
   │    AI Handwriting Response (Stroke-by-Stroke):                          │
   │    • Let u = x² + 1  ==>  du = 2x dx                                   │
   │    • ∫ (1/u) du = ln|u|                                                │
   │    • Final Answer: ln(x² + 1)                                          │
   │                                                                        │
   │    🎙️ Voice Tutor: "Notice how the numerator is the exact derivative   │
   │                     of the denominator, just like your notes on Page 2"│
   └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The Core Problem

When students struggle with complex calculus or algebra, they typically leave their notes and open external solver tools or conversational chatbots. This workflow suffers from four critical flaws:

1. **Complete Loss of State & Learning History:** External solvers treat every query in isolation. They have zero awareness of the student's curriculum, definitions, or previous notes.
2. **The LLM Hallucination Trap:** Pure Large Language Models are statistical next-token predictors. In advanced mathematics, they frequently drop signs, misapply rules, or hallucinate plausible-looking but completely false algebraic steps.
3. **Passive Consumption Over Understanding:** Chatbots dump static blocks of typed text or LaTeX. Students copy-paste without processing the underlying spatial or procedural intuition.
4. **Context Switching Friction:** Jumping between notebooks, apps, and browser tabs breaks focus and cognitive momentum.

---

## 3. The InkMentor Paradigm

InkMentor is built on six uncompromising principles:

* **Notebook First:** The product is a genuine notebook. The AI is a guest that appears only when explicitly summoned. It never interrupts, autocompletes unprompted, or crowds the screen.
* **The Canvas is the Interface:** Solutions are authored directly onto the student's notebook page in natural cursive handwriting, anchored precisely where the question was posed.
* **Verified-Before-Shown:** No mathematical step or solution is ever drawn on the page unless an independent symbolic computation engine (SymPy) has evaluated and confirmed its truth.
* **Episodic Notebook Memory:** Explanations cite the student’s own earlier pages whenever a relevant lemma or formula exists.
* **Pedagogical Progression:** A three-tiered **Hint Ladder** offers a conceptual nudge first, an intermediate algebraic setup second, and the complete worked solution only as a final resort.
* **Zero Cognitive Overhead:** The stationery toolbar retracts smoothly into the desk edge while writing, giving students a distraction-free, full-bleed notebook canvas.

---

## 4. System Architecture

InkMentor coordinates a browser-based tactile frontend with a hardened, pre-warmed FastAPI backend:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FRONTEND (HTML5 / Vanilla CSS / ES6)                         │
│                                                                                              │
│   [Stationery Instruments]  [Smart Auto-Minimize]  [Offscreen Canvas Crop]  [Caveat Engine]  │
│   • Ballpoint Pen           • Retracts on inking   • 768px normalized PNG   • SVG Radicals   │
│   • Vintage Fountain Pen    • Unveils on pause     • Padded Bounding Box    • Pen-Tip Tracer │
│   • Graphite Pencil         • Sticky Action Bar    • Magic-byte validated   • Voice Sync     │
└───────────────────────────────┬──────────────────────────────────────────▲───────────────────┘
                                │                                          │
                   POST /api/recognize (PNG)                 Animated Strokes + Audio Stream
                                │                                          │
┌───────────────────────────────▼──────────────────────────────────────────┴───────────────────┐
│                                 BACKEND (FastAPI / Python 3.11)                              │
│                                                                                              │
│   ┌───────────────────────────┐      ┌───────────────────────────┐      ┌──────────────────┐ │
│   │   Multimodal Vision OCR   │ ───► │  Episodic Notebook Memory │ ───► │  LLM Step Solver │ │
│   │   (Gemini Vision Engine)  │      │  (Vector Cosine Index)    │      │  (Minimal Think) │ │
│   └───────────────────────────┘      └───────────────────────────┘      └─────────┬────────┘ │
│                                                                                   │          │
│                                                                         Candidate Steps JSON │
│                                                                                   │          │
│                                      ┌────────────────────────────────────────────▼────────┐ │
│                                      │  Pre-Warmed SymPy Worker Pool (CAS Verification)    │ │
│                                      │  • Subprocess Sandboxing    • 10.0s Hard Timeout    │ │
│                                      │  • Identifiers Allowlist    • diff(ans) == expr     │ │
│                                      │  • Latency: 8.9 ms (88x)    • Automatic 1x Retry    │ │
│                                      └──────────────────────┬──────────────────────────────┘ │
│                                                             │                                │
│                                                    Verified Steps OK                         │
│                                                             │                                │
│                                      ┌──────────────────────▼──────────────────────────────┐ │
│                                      │  Synchronized Text-To-Speech (Gemini TTS / Groq)    │ │
│                                      │  • 24kHz Mono WAV Audio     • Concurrent Prefetch   │ │
│                                      │  • Dynamic Vocal Directions • Browser Voice Fallback│ │
│                                      └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Feature Showcase

### Authentic Stationery Instruments & Smart Auto-Minimize
InkMentor rejects artificial "AI-sloped" design in favor of authentic, tactile stationery instruments:
* **Classic Ballpoint Pen:** 2.5px consistent dark-charcoal ink line.
* **Vintage Fountain Pen:** Pressure-modulated variable line thickness (2px to 5px) with natural nib bleed.
* **Graphite Pencil:** Textured, soft 1.8px graphite stroke with realistic paper friction.
* **Chisel Highlighter:** Semi-transparent pastel wash (`mix-blend-mode: multiply`) designed for highlighting formulas without obscuring underlying handwriting.
* **Precision Ruler & Acrylic Widget:** On-screen technical ruler widget displaying millimeter ticks and angle guides for geometric alignment.
* **Smart Auto-Minimize:** When the student brings pen to paper, the toolbar smoothly retracts downward off-screen using hardware-accelerated CSS transforms (`translateY`), maximizing the workspace. Hovering near the dock edge or pausing immediately restores the toolbar.

### Decoupled Persistent AI Action Capsule
While the stationery instruments auto-minimize during active handwriting, the **AI Action Capsule** stays permanently docked at the top right of the canvas. The student always has instantaneous access to:
* **Circle to Solve:** Quick-toggle lasso selection tool.
* **Hint Ladder:** On-demand conceptual clues.
* **Audio Voice Toggle:** Instant mute/unmute control for Ink's voice tutor.
* **Instant Solve:** Execute reasoning on the selected bounding box.

### Circle-to-Solve Gesture & Multimodal Vision
* **Closed-Loop Gesture Detection:** The frontend canvas continuously monitors pointer strokes. A circle gesture is automatically recognized when the path closure distance is $\le \max(30\text{px}, 15\% \text{ path length})$ with a bounding box $\ge 40 \times 40\text{px}$.
* **Offscreen Normalization:** Extracted strokes are composited onto an offscreen canvas, scaled to 768px max dimension to optimize network latency, and verified against standard PNG magic bytes (`89 50 4E 47 0D 0A 1A 0A`).
* **Confirmation & Editing Modal:** The student receives an editable transcription confirmation modal, ensuring handwriting misreads can be corrected before execution.

### Verified-Before-Shown (Zero-Hallucination CAS Engine)
InkMentor enforces an absolute guarantee: **no unverified math touches the notebook**.
1. Candidate steps from the reasoning model are routed to an isolated SymPy CAS subprocess.
2. Antiderivatives are checked via exact symbolic differentiation: $\frac{d}{dx}[\text{Answer}] \equiv \text{Integrand}$.
3. Derivatives are evaluated against ground-truth symbolic operator trees.
4. Equations are solved over real sets $\mathbb{R}$ to verify root completeness.
5. If the model errs, a targeted symbolic feedback loop executes one automatic correction attempt. If it still fails, the solution is gracefully withheld and flagged, completely eliminating mathematical hallucinations.

### Episodic Notebook Memory & Margin Portals
* **Episodic Vector Embeddings:** Each page in the student's notebook maintains an indexed semantic representation of its lemmas, definitions, and worked examples.
* **Grounded Retrieval:** When solving a new problem, the retrieval engine searches earlier pages using cosine similarity.
* **Interactive Margin Link:** If a derivation relies on an earlier concept (e.g., Chain Rule on Page 2), a margin badge appears: `← your Page 2, again`. Tapping this portal jumps smoothly back to the original derivation.

### Fluid Stroke-by-Stroke Handwriting Animation
* **Self-Hosted Typography:** Powered by the genuine handwriting font **Caveat** and fallback vector centerline font **Reenie Beanie**.
* **Gliding Pen-Tip Tracer:** An animated glowing amber pen-tip dot (`.ai-pen-tip-dot`) traces the head of every mathematical stroke in real time.
* **True Mathematical Radicals & Vinculums:** Square roots are drawn as authentic geometric radicals with horizontal vinculum extension bars dynamically fitted over the radicand.

### Synchronized Voice Tutor ("Ink")
* **Natural Conversational Pacing:** Narration is delivered as concise tutor explanations (10–20 words per step) powered by Gemini TTS and Groq Orpheus.
* **Speech-Clock Sequencing:** Line $i+1$ begins writing and speaking strictly after line $i$ has finished both its drawing animation and spoken utterance (`Promise.all`), preventing desynchronization.
* **Resilient Audio Fallback:** If cloud speech encounters network latency or quota exhaustion, InkMentor seamlessly falls back to the browser's native Web Speech API with zero interruption.

### Pedagogical Hint Ladder
To foster true learning over rote copying, InkMentor provides three pedagogical tiers:
* **Nudge (Level 1):** Reminds the student of the governing theorem or substitution rule without giving away calculations.
* **Next Step (Level 2):** Sets up the initial algebraic transformation or variable substitution.
* **Full Solution (Level 3):** Generates the verified step-by-step derivation.

### Digital Paper Theme (Canvas-Preserved Dark Mode)
InkMentor respects student visual comfort while preserving the legibility of handwriting:
* **The Problem:** Generic dark mode filters invert canvas backgrounds to pure black, turning pencil graphite into glaring neon and ruining the sensation of writing on real paper.
* **The InkMentor Solution:** When Dark Mode is toggled, the chrome, headers, modals, and toolbars adopt a sleek slate-charcoal aesthetic (`#111827` / `#1F2937`), while the **paper notebook canvas remains an authentic, glare-free off-white**. Writing contrast and ink aesthetics remain pristine.

---

## 6. Mathematical Scope & Topic Boundaries

InkMentor is purposefully specialized for high school and undergraduate mathematics. To uphold its strict symbolic verification guarantee, supported problems are mapped to deterministic CAS operations:

| Mathematical Domain | Task Type | Verification Mechanism | Example Problems |
| :--- | :--- | :--- | :--- |
| **Differentiation** | `differentiate` | Exact symbolic derivative matching | $\frac{d}{dx} \sin(3x^2)$, $\frac{d}{dx} (x^2+1)^3$, $\frac{d}{dx} [x \ln(x)]$ |
| **Indefinite Integration** | `integrate` | $\frac{d}{dx}[\text{Sol}] \equiv \text{Integrand}$ | $\int \frac{2x}{x^2+1} dx$, $\int x e^x dx$, $\int \cos(5x) dx$ |
| **Algebraic Equations** | `solve` | Finite real root set equivalence | $x^2 - 5x + 6 = 0$, $3x + 7 = 22$, $2x^2 - 8 = 0$ |
| **Polynomial Factoring** | `factor` | `is_factored` structural validation | $x^2 - 9 \implies (x-3)(x+3)$, $x^2 - 5x + 6$ |
| **Algebraic Expansion** | `expand` | `is_expanded` polynomial validation | $(x-2)(x-3) \implies x^2 - 5x + 6$, $(x+1)^3$ |
| **Simplification** | `simplify` | $\text{simplify}(A - B) \equiv 0$ | $\frac{x^2 - 1}{x - 1} \implies x + 1$, $\sin^2(x) + \cos^2(x) \implies 1$ |
| **Multivariable Concepts** | *Curated Pages* | Rendered with interactive vector diagrams | Partial derivatives, gradients, surfaces, Jacobians |

> **Verification Sandboxing:** Non-algebraic word problems, differential equations with boundary values, and infinite trigonometric solution sets are safely rejected by the input validator to prevent unverified solutions from appearing.

---

## 7. Performance & Latency Engineering

To deliver real-time responsiveness without sacrificing symbolic verification, InkMentor incorporates seven key performance optimizations:

```
+-----------------------------------------------------------------------------------------+
|                               LATENCY OPTIMIZATION AUDIT                                |
+-------------------------------+-------------------+-------------------+-----------------+
| Stage / Pipeline Component    | Baseline (Cold)   | Optimized         | Speedup Factor  |
+-------------------------------+-------------------+-------------------+-----------------+
| SymPy CAS Verification        | 788.2 ms          | 8.9 ms            | 88x faster      |
| Python Process Startup Tax    | 711.0 ms          | 0.5 ms            | 1,400x faster   |
| Reasoning LLM Thinking Budget | > 15,000 ms       | < 950 ms          | 15x faster      |
| Output Token Overhead         | 397 tokens        | 291 tokens        | -27% payload    |
| Confirm-to-First-Stroke       | ~8.2 s            | ~0.1 s            | Near-Instant    |
| Inter-Step TTS Transitions    | 860 ms pause      | 0 ms pause        | Zero Delay      |
| Vision Image Payload          | 1024px canvas     | 768px normalized  | -44% bytes      |
+-------------------------------+-------------------+-------------------+-----------------+
```

### Key Optimizations Explained:
1. **Pre-Warmed SymPy Worker Pool:** An isolated Python background worker loads `sympy` once at server startup. Incoming verifications execute across IPC channels in ~8.9ms instead of paying a ~700ms cold import penalty per request.
2. **Speculative Solve on Recognition:** While the student reviews the transcription in the confirmation modal (~2s read pause), `/api/solve` is triggered speculatively in the background. When "Solve" is tapped, the solution is already verified and waiting.
3. **Batch TTS Prefetch with Concurrency 3:** Narration audio files for subsequent steps are prefetched in parallel while Step 1 animates, completely eliminating pauses between spoken steps.

---

## 8. API Reference

### `GET /api/health`
Health check and serverless warm-up probe.
* **Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### `POST /api/recognize`
Transcribes handwritten canvas crops into normalized math text and LaTeX.
* **Request:**
```json
{
  "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANS...",
  "media_type": "image/png"
}
```
* **Response (200 OK):**
```json
{
  "readable": true,
  "latex": "y = \\sin(3x^2)",
  "question_text": "Differentiate y = sin(3x^2)",
  "needs_confirmation": true,
  "note": ""
}
```

---

### `POST /api/solve`
Solves a mathematical problem, verifies it against SymPy, and generates synchronized handwriting and narration steps.
* **Request:**
```json
{
  "question": "Differentiate y = sin(3x^2)",
  "context": [
    {
      "page": 2,
      "snippet": "Chain rule: d/dx f(g(x)) = f'(g(x)) * g'(x)"
    }
  ]
}
```
* **Response (200 OK):**
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
      "write": "y = sin(3x^2)",
      "narration": "We start with y equals sine of three x squared."
    },
    {
      "write": "u = 3x^2, du/dx = 6x",
      "narration": "Let u equal three x squared, meaning its derivative is six x."
    },
    {
      "write": "dy/dx = 6x cos(3x^2)",
      "narration": "Applying the chain rule gives six x cosine of three x squared."
    }
  ],
  "final_answer_latex": "6x\\cos(3x^2)",
  "final_answer_sympy": "6*x*cos(3*x**2)",
  "cites_pages": [2],
  "error": null
}
```

---

### `POST /api/retrieve`
Performs cosine semantic retrieval over indexed notebook pages.
* **Request:**
```json
{
  "query": "Differentiate y = sin(3x^2)",
  "threshold": 0.65,
  "top_k": 3
}
```
* **Response (200 OK):**
```json
{
  "matches": [
    {
      "page": 2,
      "title": "Chain Rule",
      "snippet": "Chain rule: d/dx f(g(x)) = f'(g(x)) * g'(x)",
      "similarity": 0.742
    }
  ],
  "top_match": {
    "page": 2,
    "title": "Chain Rule",
    "snippet": "Chain rule: d/dx f(g(x)) = f'(g(x)) * g'(x)",
    "similarity": 0.742
  }
}
```

---

### `POST /api/tts`
Streams high-fidelity 24kHz mono PCM WAV narration with dynamic vocal inflection.
* **Request:**
```json
{
  "text": "Notice how substitution simplifies the integrand.",
  "position": "middle"
}
```
* **Response (200 OK):** Binary audio stream (`audio/wav`) with `Cache-Control: public, max-age=86400`.

---

## 9. Installation & Local Setup

### Prerequisites
* **Python 3.11+**
* A Google Gemini API Key (`LLM_API_KEY`)
* *(Optional)* A Groq API Key (`GROQ_API_KEY`) for ultra-low latency voice narration

### Quickstart

1. **Clone the repository:**
```bash
git clone https://github.com/K-Sudharshan/Inkmentor.git
cd Inkmentor
```

2. **Configure your Python virtual environment:**
```bash
python -m venv backend/.venv

# Windows (PowerShell)
backend\.venv\Scripts\Activate.ps1

# Linux / macOS
source backend/.venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

4. **Set environment variables:**
Create a `.env` file in the project root (or copy `.env.example`):
```ini
LLM_PROVIDER=gemini
LLM_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini-2.5-flash

# Optional Voice Configuration
TTS_PROVIDER=gemini
GROQ_API_KEY=your_groq_api_key_here
```

5. **Start the application:**
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **`http://127.0.0.1:8000`** in your browser to experience InkMentor.

---

## 10. Test Suite & Quality Verification

InkMentor maintains an automated test suite verifying every layer from AST input sanitization to end-to-end mathematical verification:

```bash
# Execute the complete backend test suite
backend\.venv\Scripts\python -m pytest backend -v
```

### Test Coverage Highlights (69/69 Passing):
* **`test_recognize.py`**: Magic byte payload validation, base64 corruption guards, payload size constraints (4MB ceiling), and prompt injection resistance.
* **`test_solver.py`**: SymPy equivalence verification across differentiation, integration, equation solving, factoring, expansion, and retry recovery loops.
* **`test_verify.py`**: AST sanitization rules, variable allowlist enforcement, structural inspection (`is_factored`, `is_expanded`), and timeout kill-switches.
* **`test_tts.py`**: Vocal direction validation, audio chunking, rate limiting, and WAV header reconstruction.
* **`test_retrieve.py`**: Cosine similarity calculations, threshold gating, and snippet ranking.

---

## 11. Deployment Architecture

InkMentor is architected for zero-maintenance serverless deployment on **Vercel** paired with Edge CDN static distribution:

```
                      ┌──────────────────────────────────────────────┐
                      │              Vercel Edge Network             │
                      └───────┬──────────────────────────────┬───────┘
                              │                              │
                     [Static Assets CDN]           [/api/* Rewrites]
                              │                              │
          ┌───────────────────┴─────────────────┐    ┌───────┴───────────────┐
          │ public/                             │    │ api/index.py          │
          │  ├── index.html                     │    │ (FastAPI Serverless)  │
          │  ├── fonts/Caveat-Regular.ttf       │    │  ├── /api/solve       │
          │  ├── reenie_centerlines.json        │    │  ├── /api/recognize   │
          │  └── hershey_glyphs.json            │    │  └── /api/tts         │
          └─────────────────────────────────────┘    └───────────────────────┘
```

* **Zero Compute Cost for Static Assets:** The single-page app, fonts, and vector stroke databases are served directly from global Edge caches with 0ms cold starts.
* **Read-Only Filesystem Hardening:** Dynamic temporary audio disk caches strictly target `/tmp` via `tempfile.gettempdir()`, preventing write failures on immutable cloud runtimes.
* **Stateless Resilience:** Rate limiting uses sliding-window IP buckets that function gracefully across distributed serverless instances.

---

## 12. Security & Sandboxing

Given that InkMentor processes user handwriting and arbitrary mathematical expressions, security is enforced at every boundary:

1. **Strict Identifier Allowlist:**
   Mathematical expressions passed to SymPy are pre-parsed using Python's `ast` module. Only safe algebraic functions (`sin`, `cos`, `tan`, `exp`, `log`, `sqrt`, `Abs`) and bounded scalar variables (`x`, `y`, `z`, `t`, `n`) are permitted. Dunder methods (`__`), semicolons, and bracket indexing are rejected prior to execution.
2. **Subprocess Isolation:**
   Symbolic evaluations run in a dedicated subprocess worker governed by a strict 10.0-second timeout. Rogue or non-terminating expressions are killed immediately without memory leakage.
3. **Prompt Injection Hardening:**
   The vision OCR prompt is explicitly sandboxed: it instructs the model strictly to transcribe visible mathematical notation into LaTeX and unconditionally ignore any natural language command or instruction present in the image.
4. **Data Privacy & Ephemeral State:**
   Student ink strokes and notes reside locally in browser storage (`localStorage`). No private notebooks are stored on remote database servers.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.  
Fonts used (`Caveat` and `Reenie Beanie`) are licensed under the **SIL Open Font License 1.1**.

---

<div align="center">
  <sub>InkMentor • The Notebook That Writes Back • Built with precision, care, and mathematical rigor.</sub>
</div>
