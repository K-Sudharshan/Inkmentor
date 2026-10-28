# InkMentor Vercel Hobby Deployment Guide

This guide provides step-by-step instructions for deploying InkMentor on the **Vercel Hobby (Free)** tier as a single FastAPI serverless function paired with static asset edge delivery.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────────────┐
                      │              Vercel Edge Network             │
                      └───────┬──────────────────────────────┬───────┘
                              │                              │
                     [Static Assets CDN]           [/api/* Rewrites]
                              │                              │
          ┌───────────────────┴─────────────────┐    ┌───────┴───────────────┐
          │ public/                             │    │ api/index.py          │
          │  ├── index.html                     │    │ (FastAPI App)         │
          │  ├── seed_embeddings.json           │    │  ├── /api/solve       │
          │  └── fonts/Caveat-Regular.ttf       │    │  ├── /api/recognize   │
          │                                     │    │  ├── /api/retrieve    │
          │                                     │    │  ├── /api/tts         │
          │                                     │    │  └── /api/health      │
          └─────────────────────────────────────┘    └───────────────────────┘
```

- **Static Frontend**: Edge CDN serves `public/index.html`, fonts, and glyph JSON assets globally with 0ms serverless function invocation cost.
- **FastAPI Function**: A single serverless function at `api/index.py` handles all `/api/*` routes.
- **Stateless & Resilient**: In-memory rate limiting and circuit breakers function gracefully per serverless instance; hard timeouts prevent blocked invocations.

---

## 1. Prerequisites

1. A [Vercel Account](https://vercel.com/signup) (Hobby tier is free).
2. [Node.js](https://nodejs.org/) installed locally (includes `npx`).
3. Active API keys for:
   - **Google Gemini** (`LLM_API_KEY`) – required for math reasoning and vision transcription.
   - **Groq** (`GROQ_API_KEY`) – optional/recommended for ultra-low latency voice narration.

---

## 2. Environment Variables Reference

Configure these in the **Vercel Project Dashboard** (`Settings` -> `Environment Variables`) or via the Vercel CLI. **Never commit actual secret values into git.**

| Variable Name | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `gemini` | Primary LLM provider |
| `LLM_API_KEY` | Yes | *None* | Gemini API Key |
| `LLM_MODEL` | No | `gemini-2.5-flash` | Reasoning model for `/api/solve` and vision `/api/recognize` |
| `GROQ_API_KEY` | Recommended | *None* | Groq API Key for Orpheus TTS |
| `TTS_PROVIDER` | No | `gemini` | Default TTS provider (`gemini` or `groq`) |
| `TTS_API_KEY` | No | *None* | Dedicated Gemini key for TTS (spares solver quota) |
| `LLM_TTS_MODEL` | No | `gemini-3.8-flash-tts` | Gemini TTS model |
| `GROQ_TTS_MODEL` | No | `canopylabs/orpheus-v1-english` | Groq TTS model |
| `TTS_VOICE` | No | `autumn` | Voice selection (`autumn` for Groq; `Puck` for Gemini) |
| `TTS_DIRECTION` | No | `playfully` | Default vocal direction |
| `TTS_DIRECTION_FIRST`| No | `cheerful` | Vocal direction for first step |
| `TTS_DIRECTION_LAST` | No | `warmly` | Vocal direction for final step |
| `TTS_RATE_PER_MIN` | No | `40` | Per-IP rate limit for voice generation |
| `TTS_TIMEOUT_SECONDS`| No | `8.0` | Individual TTS provider timeout |
| `TTS_DISABLE_GEMINI` | No | `false` | **Kill switch**: set `true` to immediately bypass Gemini TTS with 0 cost |
| `TTS_DISABLE_GROQ` | No | `false` | **Kill switch**: set `true` to immediately bypass Groq TTS |
| `TRUST_PROXY_HEADERS`| Yes (Vercel)| `true` | Enables real client IP detection via `x-forwarded-for` behind Vercel proxy |
| `MAX_IMAGE_BYTES` | No | `3145728` | Image byte limit (3MB keeps base64 payload under Vercel's 4.5MB limit) |
| `ENABLE_DEEP_HEALTH` | No | `false` | Enables live external provider ping via `/api/health/deep` |
| `USE_SYMPY_WORKER_POOL`| No | `true` | SymPy worker pool with automatic subprocess fallback |

---

## 3. Step-by-Step Deployment (CLI Method)

### Step 3.1: Login to Vercel
Open your terminal in the project root:
```bash
npx vercel login
```
Follow the browser prompt to authenticate.

### Step 3.2: Link Local Directory to a Vercel Project
```bash
npx vercel link
```
- Select your Vercel Scope / Team.
- Link to existing project? Answer `N` (create new).
- Project name: `inkmentor` (or your preferred name).
- Code located in: `./`.

### Step 3.3: Add Environment Variables
Add each variable securely to your Vercel project:
```bash
npx vercel env add LLM_API_KEY production
npx vercel env add LLM_API_KEY preview

npx vercel env add GROQ_API_KEY production
npx vercel env add GROQ_API_KEY preview

npx vercel env add TRUST_PROXY_HEADERS production
# Value: true
npx vercel env add TRUST_PROXY_HEADERS preview
# Value: true
```
*(Optionally add `TTS_DISABLE_GEMINI`, `LLM_MODEL`, etc.)*

### Step 3.4: Deploy Preview Build
```bash
npx vercel
```
Vercel will build and upload your project and return an ephemeral preview URL (e.g. `https://inkmentor-<hash>-<team>.vercel.app`).

### Step 3.5: Run Automated Smoke Tests on the Preview URL
Run the included smoke test script to verify all static assets and serverless APIs:
```bash
python scripts/smoke_prod.py https://inkmentor-<hash>-<team>.vercel.app
```
To run TTS checks as well (uses 1 quota request):
```bash
python scripts/smoke_prod.py https://inkmentor-<hash>-<team>.vercel.app --tts
```

### Step 3.6: Promote to Production
Once the preview passes:
```bash
npx vercel --prod
```
Your app will be live at `https://<project-name>.vercel.app`.

---

## 4. Dashboard Method (Alternative to CLI)

1. Push your repository to GitHub / GitLab.
2. In the [Vercel Dashboard](https://vercel.com/dashboard), click **"Add New Project"** -> **"Import Git Repository"**.
3. Configure the Project:
   - **Framework Preset**: `Other`
   - **Root Directory**: `./`
   - **Build Command**: *(leave blank)*
   - **Output Directory**: `public`
4. Expand **Environment Variables** and add:
   - `LLM_API_KEY`
   - `GROQ_API_KEY`
   - `TRUST_PROXY_HEADERS` = `true`
5. Click **Deploy**.

---

## 5. Deployment Protection & Making Production Public

> [!IMPORTANT]
> **Which URL to give judges:** Always provide the **Production URL** (`https://inkmentor.vercel.app`), NOT preview branch URLs.

### How to Ensure the Production URL is Public:
1. Go to your Project in the **Vercel Dashboard**.
2. Navigate to **Settings** -> **Deployment Protection**.
3. Under **Vercel Authentication**:
   - Ensure the protection scope is set to **"Only Preview Deployments"** (Standard Protection) or **Disabled**.
   - If set to "All Deployments", visitors will be prompted to log into Vercel. Change it so production is unconstrained.
4. **How to Verify**:
   - Open a new **Incognito / Private Window** in your browser.
   - Navigate to `https://<your-project>.vercel.app/`.
   - Confirm that the InkMentor notebook loads immediately without a Vercel login screen or password prompt.

---

## 6. How to View Real-Time Logs

1. **Vercel Dashboard**:
   - Go to your Project -> Click the **Logs** tab (or **Runtime Logs** under the deployment).
   - Filter by status code (e.g., `500`, `429`) or search for `[TIMING]`, `[Voice Arbiter]`, or `SymPy`.
2. **Vercel CLI**:
   ```bash
   npx vercel logs <deployment-url-or-domain>
   ```

---

## 7. Redeployments and Rollbacks

### Redeploying:
- **CLI**: Run `npx vercel --prod` to trigger a new production build.
- **Git**: Push a new commit to your `main` branch.

### Instant Rollbacks:
If a deployment ever introduces an unexpected regression:
1. In the Vercel Dashboard, go to **Deployments**.
2. Locate the last known good deployment.
3. Click the three dots (`...`) on the right -> select **"Instant Rollback"**.
4. Vercel immediately redirects traffic back to the previous build in < 1 second with zero build delay.

---

## 8. Warming the App Before a Live Demo

Serverless containers on Vercel spin down after an idle period. To ensure the first user action during a live presentation is instant:

1. **2 minutes before the presentation**, run the automated smoke test:
   ```bash
   python scripts/smoke_prod.py https://<your-production-domain>.vercel.app
   ```
2. Or open the production URL in your browser:
   - The frontend automatically pings `GET /api/health` on page load to pre-warm the serverless container.
   - If the container is cold, an unobtrusive `"Waking up the server..."` pill appears at the top for a couple of seconds and automatically dismisses once warm.

---

## 9. Post-Deployment Verification Checklist

- [ ] `GET /` serves HTML and loads the Caveat handwriting font.
- [ ] `GET /api/health` returns HTTP 200 with `{"status": "ok", "keys": {...}}`.
- [ ] Draw a math problem on the canvas, circle it, and verify transcription via `/api/recognize`.
- [ ] Click **Solve** and verify:
  - SymPy verification succeeds (`verified: true`).
  - Animated cursive pen writing renders onto the canvas.
  - Narration audio plays clearly without overlapping.
- [ ] Open in an Incognito window to confirm no Vercel login is required.
- [ ] Verify that `scripts/smoke_prod.py <URL>` passes 100%.
