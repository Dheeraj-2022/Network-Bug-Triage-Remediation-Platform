#!/usr/bin/env python3
"""
Network Bug Triage & Remediation Platform - FastAPI Backend

High-performance ASGI backend providing:
  - Full telemetry ingestion, synthetic fault injection, and triage pipeline
  - Rule-based, NLP-based, and XGBoost machine-learning triage execution
  - Multi-agent AI reasoning (Gemini/Vertex AI or graceful heuristic degradation)
  - Remediation proposal, human-approval workflow, and audit logging
  - CORS support for future React UI (http://localhost:5173)
  - Auto-generated OpenAPI / Swagger documentation (/docs and /redoc)
  - Backward-compatible serving of existing templates/dashboard.html at /

Usage:
    uvicorn main:app --reload --port 8000
    or:
    python main.py
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from api.routes import router as api_router

# ---------------------------------------------------------------------------
# App Initialization & Metadata
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Network Bug Triage & Remediation Platform API",
    description=(
        "Automated detection, correlation, and remediation platform for "
        "network and RDMA kernel issues across distributed infrastructure."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
# Configured for upcoming React frontend (Vite defaults to localhost:5173)
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Allow custom origins from environment variable if provided
env_origins = os.environ.get("NBT_CORS_ORIGINS")
if env_origins:
    allowed_origins.extend([origin.strip() for origin in env_origins.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount Routers
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix="/api")

# ---------------------------------------------------------------------------
# Root / Dashboard Endpoint
# ---------------------------------------------------------------------------
DASHBOARD_HTML_PATH = ROOT / "templates" / "dashboard.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    """
    Serve the existing single-page dashboard at root.
    Preserves full immediate UI functionality on the FastAPI server port.
    """
    if DASHBOARD_HTML_PATH.exists():
        return FileResponse(DASHBOARD_HTML_PATH, media_type="text/html")
    return HTMLResponse("<h2>Network Bug Triage Platform API is running. Visit <a href='/docs'>/docs</a>.</h2>")


# ---------------------------------------------------------------------------
# Server Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(ROOT / "logs", exist_ok=True)
    os.makedirs(ROOT / "controller" / "models", exist_ok=True)

    host = os.environ.get("NBT_FASTAPI_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("NBT_FASTAPI_PORT", "8000"))
    except ValueError:
        port = 8000

    print("=" * 64)
    print("  Network Bug Triage & Remediation Platform — FastAPI")
    print(f"  Interactive Docs (Swagger) : http://{host}:{port}/docs")
    print(f"  Alternative Docs (ReDoc)   : http://{host}:{port}/redoc")
    print(f"  Live Web Dashboard         : http://{host}:{port}/")
    print("=" * 64)

    uvicorn.run("main:app", host=host, port=port, reload=True)
