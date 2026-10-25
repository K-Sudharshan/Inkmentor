import os
import sys

# Ensure repository root is on sys.path so backend module resolves
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.main import app

# Export app for Vercel Python serverless runtime
__all__ = ["app"]
