import json
import os
import sys

from dotenv import load_dotenv
import httpx

# Load local .env if available
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

BASE_URL = os.environ.get("INKMENTOR_BACKEND_URL", "http://localhost:8000")


def main():
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        print("[smoke.py] Skipping live call: LLM_API_KEY is not set in environment or .env file.")
        print("[smoke.py] To run live, export LLM_API_KEY, LLM_PROVIDER=gemini, and LLM_MODEL.")
        sys.exit(0)

    print(f"[smoke.py] Checking health at {BASE_URL}/api/health...")
    try:
        health_resp = httpx.get(f"{BASE_URL}/api/health", timeout=5.0)
        health_resp.raise_for_status()
        print(f"[smoke.py] Server health: {health_resp.json()}")
    except Exception as exc:
        print(f"[smoke.py] Unable to reach backend server at {BASE_URL}: {exc}")
        print("[smoke.py] Make sure the server is running with: uvicorn backend.main:app --port 8000")
        sys.exit(1)

    question = "Q3. Differentiate y = sin(3x²)"
    print(f"\n[smoke.py] Step 1: Sending POST {BASE_URL}/api/retrieve for question: {question}")
    retrieve_payload = {
        "query": question,
        "threshold": 0.65,
        "top_k": 2,
    }
    context_pages = []
    try:
        ret_resp = httpx.post(f"{BASE_URL}/api/retrieve", json=retrieve_payload, timeout=15.0)
        print(f"[smoke.py] Retrieve Status: {ret_resp.status_code}")
        ret_data = ret_resp.json()
        print(f"[smoke.py] Retrieve Matches: {len(ret_data.get('matches', []))}")
        if ret_data.get("top_match"):
            print(f"[smoke.py] Top Match: Page {ret_data['top_match']['page']} ({ret_data['top_match']['title']}) - similarity: {ret_data['top_match']['similarity']}")
        context_pages = [
            {"page": m["page"], "snippet": f"{m['title']}: {m['snippet']}"}
            for m in ret_data.get("matches", [])
        ]
    except Exception as exc:
        print(f"[smoke.py] Retrieve request failed: {exc}")
        sys.exit(1)

    solve_payload = {
        "question": question,
        "context": context_pages,
    }

    print(f"\n[smoke.py] Step 2: Sending POST {BASE_URL}/api/solve with retrieved context:")
    print(json.dumps(solve_payload, indent=2))

    try:
        resp = httpx.post(f"{BASE_URL}/api/solve", json=solve_payload, timeout=30.0)
        print(f"\n[smoke.py] Solve Status: {resp.status_code}")
        print("[smoke.py] Solve Response Body:")
        print(json.dumps(resp.json(), indent=2))
    except Exception as exc:
        print(f"[smoke.py] Solve request failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
