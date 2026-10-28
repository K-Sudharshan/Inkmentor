# InkMentor

> **The notebook that writes back.**  
> A handwriting-first digital mathematics notebook powered by AI and symbolic verification.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SymPy](https://img.shields.io/badge/CAS%20Verification-SymPy%201.13-3B5526.svg?style=flat)](https://www.sympy.org/)
[![Vision & Reasoning](https://img.shields.io/badge/Vision%20%26%20Reasoning-Gemini%20Flash-4285F4.svg?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Speech Synthesis](https://img.shields.io/badge/Voice%20Tutor-Gemini%20TTS%20%7C%20Groq%20Orpheus-F55036.svg?style=flat)](https://groq.com/)
[![Test Suite](https://img.shields.io/badge/Test%20Suite-69%2F69%20Passed-brightgreen.svg?style=flat)](backend/tests/)
[![Architecture](https://img.shields.io/badge/Architecture-Verified--Before--Shown-blueviolet.svg?style=flat)](docs/ARCHITECTURE.md)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](LICENSE)

---

## The Pitch

**A handwriting-first digital mathematics notebook powered by AI and symbolic verification.**

Instead of forcing students out of their natural working environment into sterile chat boxes, InkMentor functions first and foremost as an authentic digital notebook. Students write with a stylus or mouse across authentic grid paper using handcrafted stationery tools. When they hit a roadblock, they draw a circle around their handwritten problem to summon an on-demand AI tutor. 

Every single algebraic transformation is **symbolically verified by SymPy** before it appears on the screen, authored directly onto the notebook page stroke by stroke in warm glowing ink, and explained through real-time voice mentorship.

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
3. **Retrieves earlier notes:** Episodic notebook memory searches previous pages to find related theorems, lemmas, or substitution rules.
4. **Verifies with SymPy:** A sandboxed Computer Algebra System (CAS) verifies the candidate mathematical solution before anything is rendered.
5. **Writes stroke by stroke:** InkMentor writes out the complete derivation line by line in realistic handwriting.
6. **Voice explains the intuition:** An upbeat voice study buddy named **"Ink"** synchronously explains the reasoning out loud in real time.

---

## Why It Matters: The Problem with Math AI

When students struggle with complex calculus or algebra, they typically leave their notes and open conversational chatbots. This workflow breaks learning:

* **The Hallucination Trap:** Pure Large Language Models are statistical token predictors. In mathematics, they drop negative signs, misapply rules, and invent plausible-looking algebraic steps that are factually wrong.
* **Complete Loss of Curriculum Context:** External solvers treat every query in isolation. They have zero memory of the student's textbook, teacher's definitions, or earlier notebook pages.
* **Passive Copying vs. Procedural Learning:** Chatbots dump static blocks of typed text or LaTeX. Students copy-paste without processing the spatial or procedural intuition.
* **Workflow Fragmentation:** Switching between notebooks, camera apps, and browser tabs breaks cognitive focus and study momentum.

---

## What Makes InkMentor Unique

* **Notebook-First Interface:** The notebook canvas *is* the interface. The AI is a quiet companion that appears only when explicitly summoned. It never interrupts, autocompletes unprompted, or crowds the page.
* **Circle-to-Solve Natural Gesture:** No prompt engineering, typing, or LaTeX entry. Simply draw a loop around your handwriting.
* **Verified-Before-Shown (Zero Hallucination):** No mathematical step or solution is ever drawn on the page unless an independent symbolic computation engine (SymPy) has evaluated and confirmed its truth.
* **Episodic Notebook Memory:** Explanations cite the student’s own earlier pages (`← your Page 2, again`). Tapping the margin portal smoothly flips back to the original theorem.
* **Synchronized Living Ink & Voice:** Step handwriting animations and voice narration are speech-clock locked, guiding the student through each step at a calm, conversational pace.

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
* **8.9 ms SymPy Verification (88x faster):** Pre-warmed background worker pool eliminates Python cold-import penalties.
* **~0.1 s Confirm-to-First-Stroke:** Speculative solve execution buffers verified steps while the student reviews transcription.
* **69/69 Automated Tests Passing:** Comprehensive test suite covering AST sandboxing, magic-byte guards, and CAS equivalence.

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

## Demo Walkthrough

1. **Explore the Prebuilt Chapter:** Flip through Pages 2 to 6 using the bottom navigation bar to review 3D surfaces, partial derivatives, and double integrals.
2. **Solve a Problem:** Flip to Page 6 (Practice Workshop) or Page 1.
3. **Write Math:** Use the Pen tool to write a calculus expression (e.g. `∫ 2x dx` or `∂/∂x [x² y]`).
4. **Circle & Solve:** Select the Circle tool and loop around your handwriting. Click **Solve** in the confirmation modal.
5. **Watch the Magic:** InkMentor writes the derivation line by line in glowing ink while "Ink" explains the intuition out loud!

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
