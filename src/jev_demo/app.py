from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jev_demo.client import key_status, reload_key
from jev_demo.recipes import RECIPES, public_recipes, run

STATIC = Path(__file__).parent / "static"
HOST = "127.0.0.1"
PORT = 8765

app = FastAPI(title="Jev Demo", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class DecideBody(BaseModel):
    recipe: str
    text: str = Field(min_length=1)
    mock: bool | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status() -> dict:
    return {"key": key_status()}


@app.get("/api/recipes")
async def recipes() -> dict:
    return {"recipes": await public_recipes()}


@app.post("/api/key/reload")
def put_key_reload() -> dict:
    return {"ok": True, "key": reload_key()}


@app.post("/api/decide")
async def decide_route(body: DecideBody) -> dict:
    if body.recipe not in RECIPES:
        raise HTTPException(status_code=404, detail="unknown recipe")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty text")
    use_mock = body.mock if body.mock is not None else not key_status()["present"]
    try:
        result = await run(body.recipe, text, mock=use_mock)
    except Exception as exc:  # noqa: BLE001 — surface SDK/network errors to the UI
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    result.pop("questions", None)
    return result


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Try Jev in a local browser.")
    parser.add_argument("--port", type=int, default=PORT, help="Local port (default: 8765)")
    args = parser.parse_args()
    print(f"Jev demo: http://{HOST}:{args.port}")
    uvicorn.run("jev_demo.app:app", host=HOST, port=args.port, reload=False)
