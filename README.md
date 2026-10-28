# InkMentor

> **The notebook that writes back.**  
> **The first zero-hallucination math notebook that mathematically proves its own work with SymPy before writing a single line on paper.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SymPy](https://img.shields.io/badge/CAS%20Verification-SymPy%201.13-3B5526.svg?style=flat)](https://www.sympy.org/)
[![Vision & Reasoning](https://img.shields.io/badge/Vision%20%26%20Reasoning-Gemini%20Flash-4285F4.svg?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Speech Synthesis](https://img.shields.io/badge/Voice%20Tutor-Gemini%20TTS%20%7C%20Groq%20Orpheus-F55036.svg?style=flat)](https://groq.com/)
[![Test Suite](https://img.shields.io/badge/Test%20Suite-69%2F69%20Passed-brightgreen.svg?style=flat)](backend/tests/)
[![Architecture](https://img.shields.io/badge/Architecture-Verified--Before--Shown-blueviolet.svg?style=flat)](docs/ARCHITECTURE.md)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

---

## The Pitch: Beyond Chatbots & Calculators

**A handwriting-first digital mathematics notebook powered by AI vision and deterministic symbolic verification.**

Every student knows the fatal flaw of modern AI: **Large Language Models hallucinate mathematics.** They drop negative signs, invent false trig identities, and present incorrect steps with total confidence. Meanwhile, chatbots force students to leave their notebooks, break their flow, and copy-paste text out of context.

**InkMentor changes the paradigm:**
1. **The Canvas is the Interface:** Students work naturally with digital ink across lined stationery paper. No typing, no prompt engineering, and no chat boxes.
2. **Circle-to-Solve Gesture:** Simply draw a loop around any handwritten problem to summon an on-demand AI tutor.
3. **Verified-Before-Shown (Zero Hallucination):** Every single algebraic transformation is proved and verified by a sandboxed Computer Algebra System (SymPy) before a single stroke touches the paper.
4. **Episodic Notebook Memory:** Explanations cite the student's own earlier notes (`← your Page 2, again`), building long-term understanding.
5. **Living Ink & Voice Mentorship:** Step-by-step derivations are authored directly onto the page in glowing ink, synchronized with an upbeat, real-time voice tutor named **"Ink"**.

---

## Why InkMentor: How It Compares

| Capability | Photo Solvers (Photomath, etc.) | Apple Math Notes (iPadOS 18) | Chatbots (ChatGPT / Claude) | **InkMentor** |
| :--- | :--- | :--- | :--- | :--- |
| **Mathematical Reliability** | Static database lookup | Basic arithmetic evaluation | Statistical guesses (hallucinates signs/rules) | **100% Symbolically Proven (SymPy CAS)** |
| **Pedagogy vs. Spoilers** | Dumps final answer immediately | Evaluates inline immediately (`= 42`) | Dumps walls of typed text | **3-Tier Hint Ladder (Nudge $\to$ Next Step $\to$ Solution)** |
| **Curriculum Context** | Zero context (isolated query) | Zero context (isolated expression) | Zero context from your notes | **Episodic Memory (Cites earlier notebook pages)** |
| **Interaction Model** | Phone camera snapshot | Stylus expression evaluator | Typing / prompt engineering | **Circle-to-Solve gesture on authentic paper canvas** |
| **Explanation Delivery** | Static printed text | None (answer only) | Typed bullet points | **Stroke-by-stroke living ink + synchronized voice tutor** |

---

## The Demo Story: How It Works

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

1. **Student writes naturally:** Write equations, derivatives, or integrals directly on lined paper using authentic pens or pencils.
2. **Circles to solve:** Switch to the Circle tool and loop around the problem. Multimodal AI vision instantly extracts the mathematics.
3. **Retrieves earlier notes:** Episodic notebook memory searches previous pages (via 3072-dimensional vector embeddings) to find related lemmas or substitution rules.
4. **Verifies with SymPy:** A pre-warmed CAS worker proves the candidate mathematical solution before anything is rendered.
5. **Writes stroke by stroke:** InkMentor authors the complete derivation line by line in realistic handwriting.
6. **Voice explains the intuition:** An upbeat voice study buddy named **"Ink"** synchronously explains the reasoning out loud in real time.

---

## System Architecture

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

### Headline Engineering Benchmarks:
* **8.9 ms SymPy Verification (88x speedup):** Pre-warmed background worker pool eliminates Python cold-import penalties.
* **~0.1 s Confirm-to-First-Stroke:** Speculative solve pipeline buffers verified steps while the student reviews transcription.
* **Security Sandboxing:** Python `ast` allowlist parsing blocks arbitrary code injection; 10.0s hard subprocess killswitches prevent CPU starvation.
* **69/69 Automated Tests Passing:** Comprehensive test suite covering AST sandboxing, magic-byte guards, and CAS equivalence.

---

## Mathematical Scope & Topic Boundaries

InkMentor is purposefully specialized for high school and undergraduate mathematics where symbolic proof is mathematically rigorous:

* **Single-Variable Calculus:** Derivatives (chain, product, quotient rules), indefinite & definite integrals, limits, and substitutions.
* **Multivariable Calculus:** Partial derivatives ($\partial f/\partial x, \partial f/\partial y$), tangent planes, surface normals, gradient vectors ($\nabla f$), directional derivatives ($D_{\hat{u}} f$), double & iterated integrals ($\iint_R f\,dA$), polar transformations ($r\,dr\,d\theta$), and the Jacobian determinant ($J(u, v)$).
* **Algebra & Equations:** Real root polynomial solving, factoring, expansion, and rational simplification.

*(Non-algebraic word problems and open-ended proofs are safely boundary-checked to uphold the zero-hallucination guarantee).*

---

## Core Features at a Glance

* **Authentic Stationery Tools:** Classic ballpoint pen, vintage fountain pen with nib bleed, graphite pencil, chisel highlighter, and precision acrylic ruler.
* **Smart Auto-Minimize:** Toolbar retracts downward off-screen the instant the pen touches paper, restoring a clean full-bleed canvas.
* **Persistent AI Action Capsule:** High-priority Circle-to-Solve, Hint, and Voice controls remain permanently accessible at the top right.
* **3-Tier Pedagogical Hint Ladder:**
  * *Level 1 (Nudge):* Conceptual reminder of the governing theorem without revealing calculations.
  * *Level 2 (Next Step):* Sets up the initial algebraic substitution or transformation.
  * *Level 3 (Full Solution):* Verified step-by-step derivation written onto the page.
* **Canvas-Preserved Dark Mode:** UI chrome, headers, and modals switch to dark charcoal (`#111827`), while the **paper notebook canvas remains an authentic, glare-free off-white**.
* **Prebuilt Multivariable Calculus Chapter:** 6 curated pages with interactive SVG diagrams covering 3D quadric surfaces, partial derivatives, tangent planes, gradient vectors, double integrals, and the Jacobian determinant.

---

## Quick Start (Run Locally in 2 Minutes)

### 1. Prerequisites
* **Python 3.11+**
* Google Gemini API Key (`LLM_API_KEY`)
* *(Optional)* Groq API Key (`GROQ_API_KEY`) for ultra-low latency voice narration

### 2. Setup & Installation
```bash
# Clone the repository
git clone https://github.com/K-Sudharshan/Inkmentor.git
cd Inkmentor

# Create and activate virtual environment
python -m venv backend/.venv

# Windows (PowerShell)
backend\.venv\Scripts\Activate.ps1
# Linux / macOS
source backend/.venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configure Environment
Create a `.env` file in the project root:
```ini
LLM_PROVIDER=gemini
LLM_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini-2.5-flash

# Optional Voice Configuration
TTS_PROVIDER=gemini
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Launch the Application
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## Evaluator Quick Walkthrough

> 💡 **Pro-Tip for Evaluators:**
> 1. **Turn your audio on!** The synchronized voice tutor is a core pillar of the experience.
> 2. **Skip mouse handwriting if on a trackpad:** Flip to **Page 1** or **Page 6 (Practice Workshop)** and simply circle the prebuilt calculus expressions with the Circle tool (`◯`) to experience the full verified derivation and voice mentorship instantly!

1. **Explore the Prebuilt Chapter:** Flip through Pages 2 to 6 using the bottom navigation bar to review 3D surfaces, partial derivatives, and double integrals.
2. **Solve a Problem:** Flip to Page 6 (Practice Workshop) or Page 1.
3. **Circle & Solve:** Select the Circle tool (`◯`) and loop around any math expression. Click **Solve** in the confirmation modal.
4. **Watch the Magic:** InkMentor writes the derivation line by line in glowing ink while "Ink" explains the intuition out loud!
5. **Test the Memory Portal:** When a solution references an earlier topic (e.g. Page 2 or Page 3), click the margin badge (`← your Page X, again`) to jump right back to the original notes.

---

## Project Documentation

For in-depth technical whitepapers, refer to the dedicated documentation:

* 📖 **[API Reference](docs/API.md)** — Complete endpoint schemas, request/response models, and status codes.
* 🏗️ **[Architecture Deep Dive](docs/ARCHITECTURE.md)** — Pre-warmed CAS worker pools, latency benchmarks, and stroke synthesis.
* 🛡️ **[Security & Sandboxing](docs/SECURITY.md)** — AST allowlists, subprocess isolation, and prompt injection guards.
* 🚀 **[Deployment Guide](DEPLOY.md)** — Serverless deployment on Vercel with zero cold-start static assets.
* 📋 **[Full Specification](InkMentor%20%E2%80%94%20Full%20Project%20Specification.md)** — Complete mathematical problem domain specifications.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.  
Handwriting fonts (`Caveat` and `Reenie Beanie`) are licensed under the **SIL Open Font License 1.1**.

---

<div align="center">
  <sub>InkMentor • The Notebook That Writes Back • Built with precision, care, and mathematical rigor.</sub>
</div>
