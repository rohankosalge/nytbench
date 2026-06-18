"""
FastAPI server for the multi-agent solve viewer.

Serves a single static page plus a tiny JSON API over the recordings produced by
`scripts/record_solve.py`. No database, no build step.

Run from the repo root:
    uvicorn viz.server:app --reload
    # then open http://127.0.0.1:8000
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
VIZ_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = ROOT / "recordings"

app = FastAPI(title="nytbench solve viewer")
app.mount("/static", StaticFiles(directory=VIZ_DIR / "static"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(VIZ_DIR / "index.html")


@app.get("/api/recordings")
def list_recordings() -> list[dict]:
    """List available recordings (filename + meta) for the picker."""
    out: list[dict] = []
    if RECORDINGS_DIR.exists():
        for path in sorted(RECORDINGS_DIR.glob("*.json"), reverse=True):
            try:
                meta = json.loads(path.read_text()).get("meta", {})
            except (json.JSONDecodeError, OSError):
                meta = {}
            out.append({"name": path.name, "meta": meta})
    return out


@app.get("/api/recordings/{name}")
def get_recording(name: str) -> JSONResponse:
    """Return one recording by filename (path-traversal safe)."""
    path = RECORDINGS_DIR / Path(name).name
    if path.suffix != ".json" or not path.is_file():
        raise HTTPException(status_code=404, detail="recording not found")
    return JSONResponse(json.loads(path.read_text()))
