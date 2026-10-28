# InkMentor Architecture Deep Dive

This document details the systems engineering, mathematical verification engine, and latency optimizations underpinning InkMentor.

---

## 1. End-to-End System Pipeline

InkMentor coordinates a zero-dependency HTML5/ES6 client with a pre-warmed, sandboxed FastAPI Python backend:

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

## 2. Symbolic Verification Architecture (SymPy CAS Engine)

Unlike conversational LLM chatbots that treat mathematics as next-token prediction, InkMentor enforces a strict **Verified-Before-Shown** invariant: no mathematical step reaches the student's notebook unless it is evaluated and proven by a Computer Algebra System (CAS).

### Verification Mechanics:
1. **Indefinite Integrals:** Evaluated via inverse symbolic differentiation:
   $$\frac{d}{dx}[\text{Candidate Answer}] \stackrel{?}{\equiv} \text{Integrand}$$
   This eliminates integration constant ambiguities and verifies mathematical equivalence even when the algebraic form differs from textbook tables.
2. **Definite & Multivariable Integrals:** Evaluated using SymPy's symbolic limit evaluators across all specified domains and coordinate systems.
3. **Derivatives & Partial Derivatives:** Matched against ground-truth symbolic operator trees.
4. **Algebraic Equations:** Checked for solution set equivalence over real numbers $\mathbb{R}$.
5. **Polynomial Factoring & Expansion:** Structurally validated via AST inspection (`is_factored`, `is_expanded`).
6. **Automatic 1x Error Feedback Loop:** If candidate steps fail verification, the solver triggers a single fast retry with targeted CAS failure feedback (e.g. *"SymPy computed -2\*x\*exp(-x\*\*2), candidate was 2\*x\*exp(-x\*\*2)"*). If the retry still fails, the solution is cleanly withheld rather than presenting flawed math.

---

## 3. Latency & Performance Engineering

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

### Key Engineering Optimizations:
1. **Pre-Warmed SymPy Worker Pool (`backend/verify.py`):**
   `sympy` requires ~700ms on Python cold start. InkMentor spins up persistent background subprocess workers at server launch that maintain pre-imported SymPy memory state. Incoming verifications execute across IPC channels in **~8.9ms (88x faster)**.
2. **Speculative Solve Execution (`InkMentor.html`):**
   While the student reviews the transcription in the confirmation modal (~2s natural reading pause), `/api/solve` is speculatively dispatched in the background. When the student clicks "Solve", the verified steps are already buffered and handwriting begins in **~100ms**.
3. **Batch TTS Prefetching with Concurrency 3 (`InkMentor.html`):**
   Audio streams for Steps 2, 3, and 4 are prefetched in parallel while Step 1 animates, completely eliminating pauses between spoken tutor steps.
4. **Canvas Offscreen Crop Normalization:**
   The client extracts only the bounding box of the circled math problem, adds a 24px padding border, and downscales to a max dimension of 768px. This reduces payload size by 44% without losing stroke detail.

---

## 4. Episodic Memory & Vector Indexing

The notebook memory system indexes all prebuilt notes using 3072-dimensional Gemini vector embeddings (`backend/seed_embeddings.json`).

- **Query Embedding:** Transcribed student questions are embedded via `call_embedding` in real time.
- **Cosine Similarity:** Similarity is computed across cached page vectors using Python's standard library `math` module (0 external dependencies).
- **Threshold Gating:** Results scoring $\ge 0.65$ cosine similarity are ranked and passed to the LLM solver as prompt context.
- **Margin Callback Portals:** When an earlier page is cited, the UI injects a dynamic portal button (`← your Page X, again`) that seamlessly flips the notebook to the referenced lemma.

---

## 5. Client Rendering & Stroke Geometry

- **Handwriting Synthesis:** Rendered using the self-hosted **Caveat** font and mathematical SVG geometry (square root radicals with dynamic vinculum bars).
- **Pen-Tip Tracer:** An amber glowing dot (`.ai-pen-tip-dot`) traces the animated pen tip across each line.
- **Speech-Clock Lockstep:** Each step's handwriting drawing duration is coordinated with the spoken audio utterance duration (`Promise.all`), preventing narration from drifting out of sync with the ink.
