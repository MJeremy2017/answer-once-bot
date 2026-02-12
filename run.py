#!/usr/bin/env python3
"""Run the Answered-Once Bot webhook server."""
from pathlib import Path

# Load .env from project root before any app code runs
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
