================================================================================
                                   INKMENTOR
                         The Notebook That Writes Back
================================================================================

A handwriting-first digital mathematics notebook powered by on-demand multimodal
AI reasoning, episodic notebook memory, and deterministic symbolic verification.

Stack:
- Python 3.11+ / FastAPI
- Symbolic CAS: SymPy 1.13 (Deterministic Verification Engine)
- Multimodal Vision & Reasoning: Google Gemini 3.5 / 2.5 Flash
- Voice Narration: Gemini TTS / Groq Orpheus
- Test Suite: 69/69 Automated Tests Passing
- License: MIT License / SIL OFL 1.1


================================================================================
TABLE OF CONTENTS
================================================================================
1. Overview & Philosophy
2. The Core Problem
3. The InkMentor Paradigm
4. System Architecture
5. Feature Showcase
   - Authentic Stationery Instruments & Smart Auto-Minimize
   - Decoupled Persistent AI Action Capsule
   - Circle-to-Solve Gesture & Multimodal Vision
   - Verified-Before-Shown (Zero-Hallucination CAS Engine)
   - Episodic Notebook Memory & Margin Portals
   - Fluid Stroke-by-Stroke Handwriting Animation
   - Synchronized Voice Tutor ("Ink")
   - Pedagogical Hint Ladder
   - Digital Paper Theme (Canvas-Preserved Dark Mode)
6. Mathematical Scope & Topic Boundaries
7. Performance & Latency Engineering
8. API Reference
9. Installation & Local Setup
10. Test Suite & Quality Verification
11. Deployment Architecture
12. Security & Sandboxing


================================================================================
1. OVERVIEW & PHILOSOPHY
================================================================================
InkMentor transforms how students engage with mathematics. Rather than forcing
students out of their natural working environment and into sterile chat interfaces,
InkMentor functions first and foremost as an authentic digital notebook. Students
write with a stylus or mouse across authentic grid paper using handcrafted
stationery tools.

When a student hits a roadblock, they circle their handwritten question and tap Solve.
InkMentor's integrated engine:
1. Transcribes handwritten math strokes into clean LaTeX via multimodal vision.
2. Retrieves relevant theorems and derivations from the student’s earlier notebook pages.
3. Derives an explicit, step-by-step solution.
4. Symbolically verifies every single mathematical transformation through a sandboxed
   SymPy Computer Algebra System (CAS) worker before rendering.
5. Writes the solution directly onto the notebook page stroke by stroke in warm,
   glowing ink, while synchronously narrating the mathematical intuition through
   a conversational voice tutor named "Ink".

   +------------------------------------------------------------------------+
   |                           STUDENT NOTEBOOK                             |
   |                                                                        |
   |    Practice Problem:                                                   |
   |    +---------------------------+                                       |
   |    |  /---------------------\  |                                       |
   |    |  | Q: int 2x/(x^2+1) dx|  |  <-- Circled by student               |
   |    |  \---------------------/  |                                       |
   |    +-------------+-------------+                                       |
   |                  |                                                     |
   |                  v                                                     |
   |    [ "<- Recall from Page 2" ]     <-- Notebook Memory Citation        |
   |                                                                        |
   |    AI Handwriting Response (Stroke-by-Stroke):                          |
   |    * Let u = x^2 + 1  ==>  du = 2x dx                                  |
   |    * int (1/u) du = ln|u|                                              |
   |    * Final Answer: ln(x^2 + 1)                                         |
   |                                                                        |
   |    Voice Tutor: "Notice how the numerator is the exact derivative      |
   |                  of the denominator, just like your notes on Page 2."  |
   +------------------------------------------------------------------------+


================================================================================
2. THE CORE PROBLEM
================================================================================
When students struggle with complex calculus or algebra, they typically leave their
notes and open external solver tools or conversational chatbots. This workflow
suffers from four critical flaws:

1. Complete Loss of State & Learning History:
   External solvers treat every query in isolation. They have zero awareness of
   the student's curriculum, definitions, or previous notes.

2. The LLM Hallucination Trap:
   Pure Large Language Models are statistical next-token predictors. In advanced
   mathematics, they frequently drop signs, misapply rules, or hallucinate
   plausible-looking but completely false algebraic steps.

3. Passive Consumption Over Understanding:
   Chatbots dump static blocks of typed text or LaTeX. Students copy-paste without
   processing the underlying spatial or procedural intuition.

4. Context Switching Friction:
   Jumping between notebooks, apps, and browser tabs breaks focus and cognitive
   momentum.


================================================================================
3. THE INKMENTOR PARADIGM
================================================================================
InkMentor is built on six uncompromising principles:

* Notebook First:
  The product is a genuine notebook. The AI is a guest that appears only when
  explicitly summoned. It never interrupts, autocompletes unprompted, or crowds
  the screen.

* The Canvas is the Interface:
  Solutions are authored directly onto the student's notebook page in natural
  cursive handwriting, anchored precisely where the question was posed.

* Verified-Before-Shown:
  No mathematical step or solution is ever drawn on the page unless an independent
  symbolic computation engine (SymPy) has evaluated and confirmed its truth.

* Episodic Notebook Memory:
  Explanations cite the student’s own earlier pages whenever a relevant lemma or
  formula exists.

* Pedagogical Progression:
  A three-tiered Hint Ladder offers a conceptual nudge first, an intermediate
  algebraic setup second, and the complete worked solution only as a final resort.

* Zero Cognitive Overhead:
  The stationery toolbar retracts smoothly into the desk edge while writing, giving
  students a distraction-free, full-bleed notebook canvas.


================================================================================
4. SYSTEM ARCHITECTURE
================================================================================

+------------------------------------------------------------------------------+
|                     FRONTEND (HTML5 / Vanilla CSS / ES6)                     |
|                                                                              |
|  [Stationery Instruments]  [Smart Auto-Minimize]   [Offscreen Canvas Crop]   |
|  * Ballpoint Pen           * Retracts on inking    * 768px normalized PNG    |
|  * Vintage Fountain Pen    * Unveils on pause      * Padded Bounding Box     |
|  * Graphite Pencil         * Sticky Action Bar     * Magic-byte validated    |
+---------------------------------------+--------------------------------------+
                                        |
                          POST /api/recognize (PNG)
                          Animated Strokes + Audio Stream
                                        |
+---------------------------------------v--------------------------------------+
|                        BACKEND (FastAPI / Python 3.11)                       |
|                                                                              |
|  +--------------------+     +--------------------+     +-------------------+ |
|  |  Vision OCR        | --> |  Notebook Memory   | --> |  LLM Step Solver  | |
|  |  (Gemini Engine)   |     |  (Vector Cosine)   |     |  (Minimal Think)  | |
|  +--------------------+     +--------------------+     +---------+---------+ |
|                                                                  |           |
|                                                        Candidate Steps JSON  |
|                                                                  |           |
|                             +------------------------------------v---------+ |
|                             |  Pre-Warmed SymPy Worker (CAS Verification)  | |
|                             |  * Subprocess Sandbox   * 10.0s Hard Timeout | |
|                             |  * Identifiers Allow    * diff(ans) == expr  | |
|                             |  * Latency: 8.9 ms (88x)* 1x Auto-Retry      | |
|                             +--------------------+-------------------------+ |
|                                                  |                           |
|                                         Verified Steps OK                    |
|                                                  |                           |
|                             +--------------------v-------------------------+ |
|                             |  Synchronized Text-To-Speech (Gemini / Groq) | |
|                             |  * 24kHz Mono WAV       * Concurrent Prefetch| |
|                             |  * Dynamic Directions   * Web Speech Fallback| |
|                             +----------------------------------------------+ |
+------------------------------------------------------------------------------+


================================================================================
5. FEATURE SHOWCASE
================================================================================

Authentic Stationery Instruments & Smart Auto-Minimize:
-------------------------------------------------------
InkMentor rejects artificial "AI-sloped" design in favor of authentic, tactile
stationery instruments:
* Classic Ballpoint Pen: 2.5px consistent dark-charcoal ink line.
* Vintage Fountain Pen: Pressure-modulated variable line thickness (2px to 5px)
  with natural nib bleed.
* Graphite Pencil: Textured, soft 1.8px graphite stroke with realistic paper friction.
* Chisel Highlighter: Semi-transparent pastel wash (mix-blend-mode: multiply)
  designed for highlighting formulas without obscuring underlying handwriting.
* Precision Ruler & Acrylic Widget: On-screen technical ruler widget displaying
  millimeter ticks and angle guides for geometric alignment.
* Smart Auto-Minimize: When the student brings pen to paper, the toolbar smoothly
  retracts downward off-screen using hardware-accelerated CSS transforms (translateY),
  maximizing the workspace. Hovering near the dock edge or pausing immediately
  restores the toolbar.

Decoupled Persistent AI Action Capsule:
---------------------------------------
While the stationery instruments auto-minimize during active handwriting, the
AI Action Capsule stays permanently docked at the top right of the canvas. The student
always has instantaneous access to:
* Circle to Solve: Quick-toggle lasso selection tool.
* Hint Ladder: On-demand conceptual clues.
* Audio Voice Toggle: Instant mute/unmute control for Ink's voice tutor.
* Instant Solve: Execute reasoning on the selected bounding box.

Circle-to-Solve Gesture & Multimodal Vision:
-------------------------------------------
* Closed-Loop Gesture Detection: The frontend canvas continuously monitors pointer
  strokes. A circle gesture is automatically recognized when the path closure
  distance is <= max(30px, 15% path length) with a bounding box >= 40x40px.
* Offscreen Normalization: Extracted strokes are composited onto an offscreen canvas,
  scaled to 768px max dimension to optimize network latency, and verified against
  standard PNG magic bytes (89 50 4E 47 0D 0A 1A 0A).
* Confirmation & Editing Modal: The student receives an editable transcription
  confirmation modal, ensuring handwriting misreads can be corrected before execution.

Verified-Before-Shown (Zero-Hallucination CAS Engine):
-----------------------------------------------------
InkMentor enforces an absolute guarantee: no unverified math touches the notebook.
1. Candidate steps from the reasoning model are routed to an isolated SymPy CAS
   subprocess.
2. Antiderivatives are checked via exact symbolic differentiation:
   diff(Answer, x) == Integrand.
3. Derivatives are evaluated against ground-truth symbolic operator trees.
4. Equations are solved over real sets (S.Reals) to verify root completeness.
5. If the model errs, a targeted symbolic feedback loop executes one automatic
   correction attempt. If it still fails, the solution is gracefully withheld and
   flagged, completely eliminating mathematical hallucinations.

Episodic Notebook Memory & Margin Portals:
------------------------------------------
* Episodic Vector Embeddings: Each page in the student's notebook maintains an
  indexed semantic representation of its lemmas, definitions, and worked examples.
* Grounded Retrieval: When solving a new problem, the retrieval engine searches
  earlier pages using cosine similarity.
* Interactive Margin Link: If a derivation relies on an earlier concept (e.g.,
  Chain Rule on Page 2), a margin badge appears: "<- your Page 2, again". Tapping
  this portal jumps smoothly back to the original derivation.

Fluid Stroke-by-Stroke Handwriting Animation:
---------------------------------------------
* Self-Hosted Typography: Powered by the genuine handwriting font Caveat and
  fallback vector centerline font Reenie Beanie.
* Gliding Pen-Tip Tracer: An animated glowing amber pen-tip dot (.ai-pen-tip-dot)
  traces the head of every mathematical stroke in real time.
* True Mathematical Radicals & Vinculums: Square roots are drawn as authentic
  geometric radicals with horizontal vinculum extension bars dynamically fitted
  over the radicand.

Synchronized Voice Tutor ("Ink"):
---------------------------------
* Natural Conversational Pacing: Narration is delivered as concise tutor explanations
  (10-20 words per step) powered by Gemini TTS and Groq Orpheus.
* Speech-Clock Sequencing: Line i+1 begins writing and speaking strictly after line i
  has finished both its drawing animation and spoken utterance (Promise.all),
  preventing desynchronization.
* Resilient Audio Fallback: If cloud speech encounters network latency or quota
  exhaustion, InkMentor seamlessly falls back to the browser's native Web Speech API
  with zero interruption.

Pedagogical Hint Ladder:
------------------------
To foster true learning over rote copying, InkMentor provides three pedagogical tiers:
* Nudge (Level 1): Reminds the student of the governing theorem or substitution rule
  without giving away calculations.
* Next Step (Level 2): Sets up the initial algebraic transformation or variable substitution.
* Full Solution (Level 3): Generates the verified step-by-step derivation.

Digital Paper Theme (Canvas-Preserved Dark Mode):
-------------------------------------------------
InkMentor respects student visual comfort while preserving the legibility of handwriting:
* The Problem: Generic dark mode filters invert canvas backgrounds to pure black,
  turning pencil graphite into glaring neon and ruining the sensation of writing
  on real paper.
* The InkMentor Solution: When Dark Mode is toggled, the chrome, headers, modals,
  and toolbars adopt a sleek slate-charcoal aesthetic (#111827 / #1F2937), while the
  paper notebook canvas remains an authentic, glare-free off-white. Writing contrast
  and ink aesthetics remain pristine.


================================================================================
6. MATHEMATICAL SCOPE & TOPIC BOUNDARIES
================================================================================

InkMentor is purposefully specialized for high school and undergraduate mathematics.
Supported problems are mapped to deterministic CAS operations:

--------------------------------------------------------------------------------
Domain                  | Task Type    | Verification Mechanism
--------------------------------------------------------------------------------
Differentiation         | differentiate| Exact symbolic derivative matching
Indefinite Integration  | integrate    | diff(Solution, x) == Integrand
Algebraic Equations     | solve        | Finite real root set equivalence
Polynomial Factoring    | factor       | is_factored structural validation
Algebraic Expansion     | expand       | is_expanded polynomial validation
Simplification          | simplify     | simplify(A - B) == 0
Multivariable Concepts  | Curated Pages| Interactive vector field & surface diagrams
--------------------------------------------------------------------------------

Verification Sandboxing: Non-algebraic word problems, differential equations with
boundary values, and infinite trigonometric solution sets are safely rejected by
the input validator to prevent unverified solutions from appearing.


================================================================================
7. PERFORMANCE & LATENCY ENGINEERING
================================================================================

+------------------------------------------------------------------------------+
|                          LATENCY OPTIMIZATION AUDIT                          |
+-------------------------------+-------------------+------------------+-------+
| Stage / Pipeline Component    | Baseline (Cold)   | Optimized        | Impact|
+-------------------------------+-------------------+------------------+-------+
| SymPy CAS Verification        | 788.2 ms          | 8.9 ms           | 88x   |
| Python Process Startup Tax    | 711.0 ms          | 0.5 ms           | 1400x |
| Reasoning LLM Thinking Budget | > 15,000 ms       | < 950 ms         | 15x   |
| Output Token Overhead         | 397 tokens        | 291 tokens       | -27%  |
| Confirm-to-First-Stroke       | ~8.2 s            | ~0.1 s           | Instant
| Inter-Step TTS Transitions    | 860 ms pause      | 0 ms pause       | 0 ms  |
| Vision Image Payload          | 1024px canvas     | 768px normalized | -44%  |
+-------------------------------+-------------------+------------------+-------+

Key Engineering Highlights:
1. Pre-Warmed SymPy Worker Pool: Loads sympy once at server startup. Incoming
   verifications execute across IPC channels in ~8.9ms instead of paying ~700ms cold tax.
2. Speculative Solve on Recognition: While the student reviews transcription in the
   confirmation modal (~2s read pause), /api/solve runs speculatively in the background.
3. Batch TTS Prefetch with Concurrency 3: Audio files for subsequent steps prefetch in
   parallel while Step 1 animates, eliminating inter-step pauses.


================================================================================
8. API REFERENCE
================================================================================

GET /api/health
----------------
Health check and serverless warm-up probe.
Response (200 OK):
{
  "status": "ok"
}

POST /api/recognize
-------------------
Transcribes handwritten canvas crops into normalized math text and LaTeX.
Request:
{
  "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANS...",
  "media_type": "image/png"
}
Response (200 OK):
{
  "readable": true,
  "latex": "y = \\sin(3x^2)",
  "question_text": "Differentiate y = sin(3x^2)",
  "needs_confirmation": true,
  "note": ""
}

POST /api/solve
---------------
Solves a problem, verifies it against SymPy, and generates synchronized steps.
Request:
{
  "question": "Differentiate y = sin(3x^2)",
  "context": [
    {
      "page": 2,
      "snippet": "Chain rule: d/dx f(g(x)) = f'(g(x)) * g'(x)"
    }
  ]
}
Response (200 OK):
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

POST /api/retrieve
------------------
Performs cosine semantic retrieval over indexed notebook pages.
Request:
{
  "query": "Differentiate y = sin(3x^2)",
  "threshold": 0.65,
  "top_k": 3
}
Response (200 OK):
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

POST /api/tts
-------------
Streams high-fidelity 24kHz mono PCM WAV narration with dynamic vocal inflection.
Request:
{
  "text": "Notice how substitution simplifies the integrand.",
  "position": "middle"
}
Response (200 OK): Binary audio stream (audio/wav).


================================================================================
9. INSTALLATION & LOCAL SETUP
================================================================================

Prerequisites:
- Python 3.11+
- Google Gemini API Key (LLM_API_KEY)
- (Optional) Groq API Key (GROQ_API_KEY) for ultra-low latency voice narration

Step 1: Clone repository
$ git clone https://github.com/K-Sudharshan/Inkmentor.git
$ cd Inkmentor

Step 2: Configure Python virtual environment
$ python -m venv backend/.venv
# Windows (PowerShell):
backend\.venv\Scripts\Activate.ps1
# Linux / macOS:
source backend/.venv/bin/activate

Step 3: Install dependencies
$ pip install -r requirements.txt
$ pip install -r requirements-dev.txt

Step 4: Configure environment variables
Create a .env file in the project root:
LLM_PROVIDER=gemini
LLM_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini-2.5-flash
TTS_PROVIDER=gemini
GROQ_API_KEY=your_groq_api_key_here

Step 5: Run the development server
$ uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
Open http://127.0.0.1:8000 in your browser.


================================================================================
10. TEST SUITE & QUALITY VERIFICATION
================================================================================
InkMentor maintains an automated test suite verifying every layer from AST input
sanitization to end-to-end mathematical verification:

$ backend\.venv\Scripts\python -m pytest backend -v

Test Coverage Highlights (69/69 Passing):
* test_recognize.py: Magic byte payload validation, base64 corruption guards,
  payload size constraints (4MB ceiling), and prompt injection resistance.
* test_solver.py: SymPy equivalence verification across differentiation, integration,
  equation solving, factoring, expansion, and retry recovery loops.
* test_verify.py: AST sanitization rules, variable allowlist enforcement, structural
  inspection (is_factored, is_expanded), and timeout kill-switches.
* test_tts.py: Vocal direction validation, audio chunking, rate limiting, and WAV
  header reconstruction.
* test_retrieve.py: Cosine similarity calculations, threshold gating, and snippet ranking.


================================================================================
11. DEPLOYMENT ARCHITECTURE
================================================================================
InkMentor is architected for zero-maintenance serverless deployment on Vercel
paired with Edge CDN static distribution:

- Zero Compute Cost for Static Assets: The single-page app, fonts, and vector stroke
  databases are served directly from global Edge caches with 0ms cold starts.
- Read-Only Filesystem Hardening: Dynamic temporary audio disk caches strictly
  target /tmp via tempfile.gettempdir(), preventing write failures on immutable runtimes.
- Stateless Resilience: Rate limiting uses sliding-window IP buckets that function
  gracefully across distributed serverless instances.


================================================================================
12. SECURITY & SANDBOXING
================================================================================
1. Strict Identifier Allowlist:
   Mathematical expressions passed to SymPy are pre-parsed using Python's ast module.
   Only safe algebraic functions (sin, cos, tan, exp, log, sqrt, Abs) and bounded
   scalar variables (x, y, z, t, n) are permitted. Dunder methods (__), semicolons,
   and bracket indexing are rejected prior to execution.
2. Subprocess Isolation:
   Symbolic evaluations run in a dedicated subprocess worker governed by a strict
   10.0-second timeout. Rogue or non-terminating expressions are killed immediately.
3. Prompt Injection Hardening:
   The vision OCR prompt is explicitly sandboxed: it instructs the model strictly
   to transcribe visible mathematical notation into LaTeX and unconditionally ignore
   any natural language command or instruction present in the image.
4. Data Privacy & Ephemeral State:
   Student ink strokes and notes reside locally in browser storage (localStorage).
   No private notebooks are stored on remote database servers.

================================================================================
License: MIT License
Fonts: SIL Open Font License 1.1 (Caveat, Reenie Beanie)
InkMentor - The Notebook That Writes Back
================================================================================
