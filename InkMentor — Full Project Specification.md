# InkMentor — Full Project Specification

*Hackathon prototype · Spec v1 · October 14, 2026 · Written so that any human or AI agent can understand the project end to end and continue building it.*

## 1. Summary

InkMentor is a **handwriting-first digital notebook** with iPad-style grid pages. It behaves exactly like a normal note-taking notebook until the student asks for help. When the student circles a math problem or taps **Solve**, an AI agent reads the handwriting, solves the problem, verifies the answer symbolically, and writes the full worked solution on the page **stroke by stroke in handwriting-style ink**, while **narrating each step by voice**.

Its signature mechanism is **notebook memory**: the agent is grounded in the student's own earlier pages, so it can say, by voice and in the margin, *"you derived this on Page 1."* Existing solvers are stateless and answer only the problem in front of them; InkMentor solves it using the student's own learning history.

**Tagline:** Ink that writes, talks and guides you.

## 2. How the idea evolved

1. **Original idea:** an AI agent that lives inside a notebook, solves complex math problems, writes the answer on the page like a human, and explains by voice while solving.
2. **Clarification:** the app is mainly for taking notes, like a physical notebook. The AI acts only when the user asks it to solve. It is never always-on or intrusive.
3. **Novelty review (honest result):** the plain concept is *not* novel. Close existing products are Photomath, Google Lens, Microsoft Math Solver, Khanmigo, Gauth, Apple Math Notes (iOS/iPadOS 18), GoodNotes, Notability, Samsung Notes and OneNote. Rated roughly 4/10 for novelty as a plain on-demand solver, 6-7/10 with synced handwriting plus voice, and about 8-9/10 with notebook memory. No idea gets a true 10/10 in this space.
4. **Recommended direction:** make the hero the combination of **notebook memory + handwriting-style output + hint ladder**, with Tamil/Tanglish voice as a bonus. Novelty comes from a new mechanism, not from more features.

## 3. Problem statement

When students get stuck on a math problem, they leave their notes and open a separate solver app. That app:

- has no memory of what the student has studied,
- dumps a typed final answer instead of working in the student's notebook,
- encourages copying rather than understanding,
- usually ignores regional languages and local syllabi.

The notebook, the one place that holds a student's real learning history, is left out of the loop completely.

## 4. Product principles

- **Notebook first.** The product is a notebook. The AI is a guest that appears only when summoned.
- **The page is the interface.** Output is written on the student's own page, not in a chat window.
- **Grounded, not generic.** Explanations should reference the student's actual earlier pages whenever retrieval finds a relevant one.
- **Verified math.** No solution is written to the page unless an independent symbolic check agrees.
- **Teach, don't dump.** A hint ladder offers a nudge first and the full solution last.
- **Honest about limits.** Never claim true handwriting style transfer unless it is actually built.

## 5. Target users

Students preparing for JEE, CBSE and state-board exams (starting with the Tamil Nadu context), plus any student who takes handwritten math notes on a tablet. Voice support targets English, Tamil/Tanglish and Hindi.

**Non-goals for the prototype:** a full-featured note-taking suite (shapes, PDF import, collaboration), always-on proactive AI, all subjects beyond math, native mobile apps, user accounts at scale.

## 6. Core user flow

1. The student opens a notebook (for example *Calculus*) and writes notes on grid pages with finger, mouse or Apple Pencil.
2. Later, on a practice page, they write a question such as *Q3. Differentiate y = sin(3x²)*.
3. They circle it (or select it) and tap **Solve**.
4. The app shows a status pill: *Reading your question… → Found the chain rule on Page 1 → Writing step 1 of 3.*
5. The AI writes each step on the page in amber-to-coral handwriting-style ink, one line at a time, while a voice reads that step.
6. A margin link appears: **"← your Page 1, again"**. Tapping it jumps to the earlier page that the explanation drew on.
7. Optionally, the student uses the hint ladder instead: a nudge, then the next step, then the full solution.

## 7. Feature set

**Must-have for the demo (hero path):** notebook with pages and pen/eraser; summon via Solve; handwriting recognition to LaTeX; LLM-generated steps; SymPy verification; notebook memory retrieval with a visible page callback; stroke-by-stroke handwriting-style writing; synced voice narration.

**Should-have:** hint ladder; handwriting font choices; Tamil/Tanglish voice.

**Future:** learned personal handwriting style; mistake tracking with personalized practice pages; circle any single step and ask "why?"; diagrams and graphs drawn stroke by stroke; multi-subject support.

## 8. System mechanisms (in detail)

### 8.1 Summon gesture

The AI runs only on request: a **Solve** button, and a circle/lasso gesture around a question. Output is anchored below the circled region.

### 8.2 Handwriting recognition

- **Input:** a cropped image of the circled region (PNG).
- **Method:** a vision-capable LLM (a model that accepts images and text, such as Claude, GPT-4o or Gemini) prompted to transcribe the math as LaTeX. Mathpix is a dedicated fallback.
- **Output:** LaTeX text, for example `y = \\sin(3x^2)`.
- **Known weakness:** confident misreads of messy handwriting. Mitigation: show the recognized expression to the user, and let them correct it before solving.

### 8.3 Reasoning and verification

- An LLM produces a structured list of steps (JSON). Each step has a LaTeX line, a short narration sentence and the handwriting text to write.
- **SymPy** (Python symbolic math library) independently computes the final answer, for example `diff(sin(3*x**2), x)` gives `6*x*cos(3*x**2)`.
- If the LLM's final answer and SymPy's answer are symbolically equal, the steps are accepted. If not, retry once with the discrepancy fed back, then flag the problem instead of writing a wrong answer.

### 8.4 Notebook memory (the hero mechanism)

- Each page stores: stroke data, a rendered image, recognized text/LaTeX, and an **embedding** (a numeric vector representing meaning).
- At solve time, embed the question, run cosine-similarity search over the student's pages, and take the top matches above a similarity threshold.
- The retrieved page number and snippet are fed to the LLM, which must cite them in the explanation ("you wrote the chain rule on Page 1"). If nothing relevant is found, the solution is written without a callback. Never invent a page reference.
- For the hackathon, an in-memory list plus NumPy cosine similarity over 8-10 pre-seeded, pre-verified pages is enough.

### 8.5 Stroke-by-stroke handwriting output

Three options, easiest first:

1. **Recommended:** a *single-line* (centerline) font such as Hershey, converted to SVG paths (opentype.js or similar). Animate each path with `stroke-dasharray` and `stroke-dashoffset`, with a pen-tip dot following the path. Add small random jitter and slant so it looks handwritten.
2. A regular handwriting font (Reenie Beanie, Caveat) revealed left to right with a clip mask. Fast, but letters wipe in instead of being drawn.
3. A generative handwriting model trained on pen-trajectory data. True style matching, but too risky for 24-48 hours.

Always describe what is built honestly, for example "handwriting-style rendering".

### 8.6 Synced voice narration

Text-to-speech per step, started at the same moment as that step's stroke animation. Set the stroke duration from the audio length so the pen finishes as the sentence ends. Supported languages: English first; Tamil/Tanglish and Hindi as the differentiator. Browser `speechSynthesis` works as a zero-cost fallback but varies by device and is often silent inside in-app viewers.

### 8.7 Hint ladder

Three levels per problem: (1) a nudge, (2) the next step only, (3) the full solution. This turns the tool from an answer-dumper into a learning tool, and it is the answer to "isn't this a cheating tool?"

### 8.8 Mistake tracking (future)

Log repeated errors (sign slips, forgetting the chain rule) across pages and generate a personalized practice page written by hand in the notebook.

## 9. Architecture and data flow

**Pipeline for one Solve action:**

1. Client captures the circled region as an image and sends it to the backend.
2. `POST /api/recognize` returns LaTeX (vision LLM or Mathpix).
3. `POST /api/retrieve` embeds the question and returns the top matching earlier pages with page numbers and snippets.
4. `POST /api/solve` calls the LLM with the question plus retrieved context and returns structured steps, then runs the SymPy check.
5. Client renders each step as animated SVG strokes and requests TTS audio for each step's narration.
6. Client plays stroke animation and audio together, then shows the margin callback link.

**Suggested data model:**

| Entity | Fields |
| --- | --- |
| Notebook | id, title, created\_at |
| Page | id, notebook\_id, number, strokes (JSON), image\_url, latex\_text, embedding (vector), created\_at |
| SolveRun | id, page\_id, question\_latex, steps (JSON), verified (bool), retrieved\_page\_ids, created\_at |

**Step JSON shape:** `{ "steps": [ { "latex": "...", "write": "...", "narration": "..." } ], "final_answer_latex": "...", "cites_pages": [1] }`

## 10. Recommended tech stack

- **Frontend:** plain HTML/JS or React with an HTML canvas for ink (tldraw is an option). Pointer Events for finger, mouse and Apple Pencil input.
- **Backend:** serverless functions (Vercel) or a small Python API (FastAPI) for SymPy.
- **Recognition:** vision LLM, with Mathpix as fallback.
- **Solver:** LLM plus SymPy verification.
- **Embeddings and retrieval:** any embedding model; storage as described in section 13.
- **Voice:** a TTS API with Tamil/Hindi support, or browser `speechSynthesis` as fallback.
- **Handwriting rendering:** Hershey single-line font to SVG paths, animated with CSS/JS.

## 11. UI/UX design specification

The look is premium, minimal and inspired by Apple design.

**Layout:**

- **Left sidebar:** a floating frosted-glass panel (backdrop blur and saturation) with a wordmark, a search field, a list of pages with mini grid thumbnails, and a "Notebook memory — 8 pages indexed" card with a softly pulsing dot. It collapses on desktop and becomes a slide-over drawer on phones.
- **Top bar:** a menu button, the page title, and a centered floating pill toolbar with pen, eraser, three ink colors (black, violet, coral), undo, a voice toggle, and a gradient **Solve** button.
- **Notebook:** a solid white page with a thin black square grid, like a professional iPad notebook. The grid is 32px on desktop and 28px on small screens. Lines are black at roughly 20 percent opacity.
- **Status pill:** a frosted pill at the bottom of the page with a small waveform and the current step text.
- **Ring:** a violet outline that appears around the question being solved.

**Typography:** system/Inter for the interface; Instrument Serif (italic accent) for the wordmark; Reenie Beanie for all handwriting.

**Color tokens:**

- Light interface: background `#f2f2f7`, glass `rgba(255,255,255,.66)`, text `#1c1c1e`, secondary text `#6e6e73`, accent `#6b4ef0`.
- Dark interface: background `#0a0a0f`, accent `#a99bff`.
- Brand palette: midnight `#05060F`, ultraviolet `#7C5CFF`, amber `#FFB347`, coral `#FF5E7E`.
- The student's ink is black. **AI ink is an amber-to-coral gradient** so the two are always visually distinct.
- The notebook page stays white in both light and dark interface modes.

**Behavior:** drawing uses Pointer Events with per-page stroke storage, undo and an eraser. Solve reveals lines with a left-to-right clip animation. The margin link ("← your Page 1, again") navigates to the referenced page.

## 12. Competitive positioning

Judges will compare InkMentor to Apple Math Notes and Photomath. The honest differences are:

- **Memory:** it uses the student's own earlier pages. Existing solvers are stateless.
- **Output surface:** the answer is written in the notebook, not shown in a chat or a one-line result.
- **Pedagogy:** a hint ladder rather than answer dumping.
- **Regional focus:** Tamil/Tanglish and Indian syllabus context.

**Do not overclaim.** Retrieval over personal notes already exists in tools such as NotebookLM and Notion AI. The defensible, specific claim is: *math solving grounded in the student's own handwritten derivations, written back onto the page.*

## 13. Feasibility and risks

**Overall feasibility:** about 8/10 for a 24-48 hour prototype if scope stays on one math domain (algebra and calculus).

| Risk | Mitigation |
| --- | --- |
| Misread handwriting | Show recognized LaTeX for confirmation; pre-test demo problems; Mathpix fallback |
| Wrong math on stage | Mandatory SymPy verification; pre-verified demo set |
| Retrieval misses on stage | Pre-seed 8-10 pages with verified OCR; test the exact callback repeatedly |
| Latency (vision, solve, TTS, animation) | Stream results; show the status pill; pre-warm calls |
| Handwriting style matching | Use handwriting-style rendering and label it honestly |
| Scope creep | Build the hero path only; everything else goes to backup slides |
| Tamil/Hindi voice quality | Treat as a bonus; keep English as the reliable default |

**Deployment issue (known):** on Vercel, a database that relies on local files fails, because serverless functions have a read-only filesystem (only temporary `/tmp`, wiped between requests). This breaks JSON-file, SQLite, ChromaDB and FAISS stored on disk. Fix options: use a hosted store such as Supabase (Postgres with pgvector), or bundle read-only seed embeddings with the deployment. If Supabase fails: set environment variables in the Vercel project settings and redeploy, use the pooled connection string (port 6543), keep the service-role key server-side only, check Row Level Security policies (empty results with no error often mean RLS with no policy), and watch function timeouts. The team decided to handle this later, during prototype building.

## 14. Hackathon strategy

**Scope:** one hero demo moment, built flawlessly. A flawless 3-minute demo of one novel idea beats six half-working features.

**Suggested build phases:**

1. **Core pipeline (first half):** handwriting in, recognition, solve with SymPy verification, animated handwritten output with voice.
2. **Hero moment (second half):** notebook memory, so a question on Page 8 reaches back to Page 1 with a visible callback.
3. **Demo hardening (last hours):** pre-seeded pages, tested demo problems, a recorded backup video in case something fails live.

**Demo script (about 3 minutes):**

1. Show pages 1-7 of notes, already written.
2. On Page 8, write or show *Q3. Differentiate y = sin(3x²)* and circle it.
3. Tap Solve; show the status pill and the solution being written with voice.
4. Point out the callback and tap "← your Page 1, again".
5. Keep the hint ladder, mistake tracking and multi-language voice as backup slides for Q&A.

**Pitch rules:**

- Open on the mechanism: a short clip of a page writing itself, with no title slide first. State the problem second.
- Avoid the word "tutor" in headlines. Use "a notebook that remembers and writes back".
- Give the Page 1 callback its own slide.
- Prepare an answer to "is this a cheating tool?" (the hint ladder).
- Label features honestly ("handwriting-style rendering"), so a live follow-up question cannot expose a gap.

## 15. Current status

| Asset | Status |
| --- | --- |
| Idea, novelty analysis, abstracts, pitch message to teammates | Done |
| UI frontend prototype (`inkmentor-app.html`, published as an interactive artifact) | Built; drawing, pages, sidebar, toolbar and a scripted Solve demo work |
| Animated demo film page (`inkmentor-demo.html`) | Built; can be screen-recorded; voice relies on device text-to-speech |
| AI-generated video (Gemini/Veo) | One 10-second clip reviewed; its math text was garbled, it switched from an iPad to a paper notebook, and the key callback was unreadable |
| Recognition, solver, SymPy, retrieval, TTS, real handwriting animation | **Not built yet** |

**Prototype limits:** Solve currently plays a scripted demo for Page 8 only. The page list and thumbnails are static samples. There is no backend.

**Lessons from the video review:** AI video models cannot render correct math text. Overlay real equations in an editor instead, keep the product visually consistent, make the Page 1 callback large and legible, and keep the waveform small so it does not cover the handwriting.

## 16. Task list for an AI agent continuing the build

Work in this order. Each task has an acceptance criterion.

1. **Recognition endpoint.** Accept a cropped canvas image; return LaTeX. *Accept when* three handwritten demo problems return correct LaTeX.
2. **Solve and verify endpoint.** Return structured steps and a verified flag using SymPy. *Accept when* a deliberately wrong LLM answer is rejected and retried.
3. **Memory index.** Embed the seeded pages and store the vectors. *Accept when* the Page 8 question retrieves Page 1 (chain rule) as the top result above threshold.
4. **Connect the UI.** Replace the scripted Solve with the real pipeline; keep the status pill and the margin callback driven by real retrieval results.
5. **Stroke animation.** Convert each step to single-line SVG strokes and animate them, timed to the narration audio. *Accept when* the pen finishes as the sentence ends.
6. **Voice.** Add a TTS provider; English first, then Tamil/Tanglish.
7. **Circle gesture.** Detect a lasso or circle around a question and crop it.
8. **Hint ladder.** Three levels per problem.
9. **Deployment.** Fix the database approach for Vercel (section 13), set environment variables and verify end to end on the deployed URL.
10. **Demo hardening.** Record a backup video and rehearse the script.

**Constraints:** keep to one math domain; never write unverified math to the page; never fabricate a page reference; keep the notebook-first, AI-on-request behavior.

## 17. Glossary

- **Vision LLM:** a language model that can read images as well as text; used to transcribe handwriting.
- **SymPy:** a free Python library for exact symbolic math; used to verify answers.
- **Embedding:** a numeric vector representing the meaning of text; used to find similar pages.
- **RAG (retrieval-augmented generation):** fetching relevant stored content and giving it to the LLM as context.
- **Single-line font:** a font whose letters are centerline paths, so they can be drawn like a pen.
- **TTS:** text-to-speech.
- **Hint ladder:** nudge, then next step, then full solution.
- **pgvector:** a Postgres extension for vector search, available through Supabase.

**Keywords:** notebook-native AI, handwriting synthesis, retrieval over personal notes, multimodal LLM, symbolic verification, EdTech, regional-language voice.
