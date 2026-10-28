================================================================================
                                   INKMENTOR
                         The Notebook That Writes Back
================================================================================

The first zero-hallucination math notebook that mathematically proves its own work
with SymPy before writing a single line on paper.

A handwriting-first digital mathematics notebook uniting multimodal AI vision,
deterministic symbolic verification, and episodic notebook memory.

Stack:
- Python 3.11+ / FastAPI 0.115
- Symbolic CAS: SymPy 1.13 (Deterministic Verification Engine)
- Multimodal Vision & Reasoning: Google Gemini Flash
- Voice Narration: Gemini TTS / Groq Orpheus
- Test Suite: 69/69 Automated Tests Passing
- License: MIT License / SIL OFL 1.1


================================================================================
THE PITCH: BEYOND CHATBOTS & CALCULATORS
================================================================================

A handwriting-first digital mathematics notebook powered by AI vision and
deterministic symbolic verification.

Every student knows the fatal flaw of modern AI: Large Language Models hallucinate
mathematics. They drop negative signs, invent false trig identities, and present
incorrect steps with total confidence. Meanwhile, chatbots force students to leave
their notebooks, break their flow, and copy-paste text out of context.

InkMentor changes the paradigm:
1. The Canvas is the Interface: Students work naturally with digital ink across
   lined stationery paper. No typing, no prompt engineering, and no chat boxes.
2. Circle-to-Solve Gesture: Simply draw a loop around any handwritten problem to
   summon an on-demand AI tutor.
3. Verified-Before-Shown (Zero Hallucination): Every single algebraic transformation
   is proved and verified by a sandboxed Computer Algebra System (SymPy) before a
   single stroke touches the paper.
4. Episodic Notebook Memory: Explanations cite the student's own earlier notes
   ("← your Page 2, again"), building long-term understanding.
5. Living Ink & Voice Mentorship: Step-by-step derivations are authored directly
   onto the page in glowing ink, synchronized with an upbeat, real-time voice
   tutor named "Ink".


================================================================================
WHY INKMENTOR: HOW IT COMPARES
================================================================================

+-----------------------+-------------------------+-------------------------+---------------------------+-----------------------------------------------+
| Capability            | Photo Solvers           | Apple Math Notes        | Chatbots                  | INKMENTOR                                     |
|                       | (Photomath, etc.)       | (iPadOS 18)             | (ChatGPT / Claude)        |                                               |
+-----------------------+-------------------------+-------------------------+---------------------------+-----------------------------------------------+
| Mathematical          | Static database lookup  | Basic arithmetic        | Statistical guesses       | 100% Symbolically Proven                      |
| Reliability           |                         | evaluation              | (hallucinates signs/rules)| (SymPy CAS)                                   |
+-----------------------+-------------------------+-------------------------+---------------------------+-----------------------------------------------+
| Pedagogy vs.          | Dumps final answer      | Evaluates inline        | Dumps walls of            | 3-Tier Hint Ladder                            |
| Spoilers              | immediately             | immediately (= 42)      | typed text                | (Nudge -> Next Step -> Solution)              |
+-----------------------+-------------------------+-------------------------+---------------------------+-----------------------------------------------+
| Curriculum            | Zero context            | Zero context            | Zero context              | Episodic Memory                               |
| Context               | (isolated query)        | (isolated expression)   | from your notes           | (Cites earlier notebook pages)                |
+-----------------------+-------------------------+-------------------------+---------------------------+-----------------------------------------------+
| Interaction           | Phone camera            | Stylus expression       | Typing / prompt           | Circle-to-Solve gesture                       |
| Model                 | snapshot                | evaluator               | engineering               | on authentic paper canvas                     |
+-----------------------+-------------------------+-------------------------+---------------------------+-----------------------------------------------+
| Explanation           | Static printed          | None                    | Typed bullet              | Stroke-by-stroke living ink                   |
| Delivery              | text                    | (answer only)           | points                    | + synchronized voice tutor                    |
+-----------------------+-------------------------+-------------------------+---------------------------+-----------------------------------------------+


================================================================================
THE DEMO STORY: HOW IT WORKS
================================================================================

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

1. Student writes naturally: Write equations, derivatives, or integrals directly
   on lined paper using authentic pens or pencils.
2. Circles to solve: Switch to the Circle tool and loop around the problem.
   Multimodal AI vision instantly extracts the mathematics.
3. Retrieves earlier notes: Episodic notebook memory searches previous pages
   (via 3072-dimensional vector embeddings) to find related lemmas or substitution rules.
4. Verifies with SymPy: A pre-warmed CAS worker proves the candidate mathematical
   solution before anything is rendered.
5. Writes stroke by stroke: InkMentor authors the complete derivation line
   by line in realistic handwriting.
6. Voice explains the intuition: An upbeat voice study buddy named "Ink"
   synchronously explains the reasoning out loud in real time.


================================================================================
SYSTEM ARCHITECTURE
================================================================================

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

Headline Engineering Benchmarks:
- 8.9 ms SymPy Verification (88x faster): Pre-warmed background worker pool
  eliminates Python cold-import penalties.
- ~0.1 s Confirm-to-First-Stroke: Speculative solve pipeline buffers verified
  steps while the student reviews transcription.
- Security Sandboxing: Python AST allowlist parsing blocks arbitrary code injection;
  10.0s hard subprocess killswitches prevent CPU starvation.
- 69/69 Automated Tests Passing: Comprehensive test suite covering AST
  sandboxing, magic-byte guards, and CAS equivalence.


================================================================================
MATHEMATICAL SCOPE & TOPIC BOUNDARIES
================================================================================

InkMentor is purposefully specialized for high school and undergraduate mathematics
where symbolic proof is mathematically rigorous:

- Single-Variable Calculus: Derivatives (chain, product, quotient rules),
  indefinite & definite integrals, limits, and substitutions.
- Multivariable Calculus: Partial derivatives (∂f/∂x, ∂f/∂y), tangent planes,
  surface normals, gradient vectors (∇f), directional derivatives (D_u f),
  double & iterated integrals (∬_R f dA), polar transformations (r dr dθ),
  and the Jacobian determinant (J(u, v)).
- Algebra & Equations: Real root polynomial solving, factoring, expansion, and
  rational simplification.

(Non-algebraic word problems and open-ended proofs are safely boundary-checked to
uphold the zero-hallucination guarantee).


================================================================================
CORE FEATURES AT A GLANCE
================================================================================

- Authentic Stationery Tools: Classic ballpoint pen, vintage fountain pen with
  nib bleed, graphite pencil, chisel highlighter, and precision acrylic ruler.
- Smart Auto-Minimize: Toolbar retracts downward off-screen the instant the pen
  touches paper, restoring a clean full-bleed canvas.
- Persistent AI Action Capsule: High-priority Circle-to-Solve, Hint, and Voice
  controls remain permanently accessible at the top right.
- 3-Tier Pedagogical Hint Ladder:
  * Level 1 (Nudge): Conceptual reminder of the governing theorem without revealing calculations.
  * Level 2 (Next Step): Sets up the initial algebraic substitution.
  * Level 3 (Full Solution): Verified step-by-step derivation written on paper.
- Canvas-Preserved Dark Mode: UI chrome and modals switch to dark slate, while
  the paper notebook canvas remains an authentic, glare-free off-white.
- Prebuilt Multivariable Calculus Chapter: 6 curated pages with interactive SVG
  diagrams covering 3D quadric surfaces, partial derivatives, tangent planes,
  gradient vectors, double integrals, and the Jacobian determinant.


================================================================================
QUICK START (RUN LOCALLY IN 2 MINUTES)
================================================================================

1. Clone the repository:
   git clone https://github.com/K-Sudharshan/Inkmentor.git
   cd Inkmentor

2. Create and activate virtual environment:
   python -m venv backend/.venv

   # Windows (PowerShell)
   backend\.venv\Scripts\Activate.ps1
   # Linux / macOS
   source backend/.venv/bin/activate

3. Install dependencies:
   pip install -r requirements.txt
   pip install -r requirements-dev.txt

4. Configure environment (.env in project root):
   LLM_PROVIDER=gemini
   LLM_API_KEY=your_gemini_api_key_here
   LLM_MODEL=gemini-2.5-flash

   # Optional Voice Configuration
   TTS_PROVIDER=gemini
   GROQ_API_KEY=your_groq_api_key_here

5. Launch application:
   uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

6. Open in browser:
   http://127.0.0.1:8000


================================================================================
EVALUATOR QUICK WALKTHROUGH
================================================================================

[!] Pro-Tip for Evaluators:
1. Turn your audio on! The synchronized voice tutor is a core pillar of the experience.
2. Skip mouse handwriting if on a trackpad: Flip to Page 1 or Page 6 (Practice Workshop)
   and simply circle the prebuilt calculus expressions with the Circle tool (◯)
   to experience the full verified derivation and voice mentorship instantly!

1. Explore the Prebuilt Chapter: Flip through Pages 2 to 6 using the bottom
   navigation bar to review 3D surfaces, partial derivatives, and double integrals.
2. Solve a Problem: Flip to Page 6 (Practice Workshop) or Page 1.
3. Circle & Solve: Select the Circle tool (◯) and loop around any math expression.
   Click "Solve" in the confirmation modal.
4. Watch the Magic: InkMentor writes the derivation line by line in glowing ink
   while "Ink" explains the intuition out loud!
5. Test the Memory Portal: When a solution references an earlier topic (e.g. Page 2
   or Page 3), click the margin badge ("← your Page X, again") to jump right back
   to the original notes.


================================================================================
PROJECT DOCUMENTATION
================================================================================

For in-depth technical whitepapers, see:
- API Reference:            docs/API.md
- Architecture Deep Dive:   docs/ARCHITECTURE.md
- Security & Sandboxing:    docs/SECURITY.md
- Deployment Guide:         DEPLOY.md
- Full Specification:       InkMentor — Full Project Specification.md


================================================================================
LICENSE
================================================================================

Licensed under the MIT License.
Handwriting fonts (Caveat and Reenie Beanie) licensed under SIL Open Font License 1.1.

InkMentor • The Notebook That Writes Back • Built with precision, care, and mathematical rigor.
