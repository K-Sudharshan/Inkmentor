import os
import sys
import traceback

# Ensure repository root is on sys.path so backend module resolves
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from backend.main import app
except Exception as exc:
    err_trace = traceback.format_exc()
    print(f"[CRITICAL STARTUP ERROR in index.py]\n{err_trace}", file=sys.stderr, flush=True)

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="InkMentor Startup Error Fallback")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    async def startup_error_fallback(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "status": "startup_error",
                "detail": f"Backend import error: {exc}",
                "traceback": err_trace.splitlines()[-6:],
            },
        )

# Export app for Vercel Python serverless runtime
__all__ = ["app"]

