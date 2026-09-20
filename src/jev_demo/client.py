"""TypeSafe key + one System One call. Questions are wire dicts."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
INPUT_PRICE_PER_MILLION = 0.042

KEY_CANDIDATES = [
    ENV_PATH,
    Path.home() / ".config" / "opencode" / "opencode-jev-orchestrator.key",
    Path.home() / ".config" / "opencode" / ".env",
    Path.home() / ".jev-gateway" / ".env",
]


def _parse_env_text(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    if "\n" not in stripped and "=" not in stripped:
        return stripped
    for line in stripped.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("TYPESAFE_API_KEY=", "JEV_KEY=", "JEV_API_KEY=")):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    return None


def resolve_key() -> str | None:
    load_dotenv(ENV_PATH, override=False)
    for name in ("TYPESAFE_API_KEY", "JEV_KEY", "JEV_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    for path in KEY_CANDIDATES:
        if not path.is_file():
            continue
        try:
            parsed = _parse_env_text(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if parsed:
            return parsed
    return None


def key_status() -> dict[str, Any]:
    key = resolve_key()
    if not key:
        return {"present": False, "hint": None, "source": None}
    return {
        "present": True,
        "hint": f"…{key[-4:]}" if len(key) >= 4 else "set",
        "source": "env",
    }


def save_key(api_key: str) -> None:
    cleaned = api_key.strip()
    if not cleaned:
        raise ValueError("empty key")
    ENV_PATH.write_text(f"TYPESAFE_API_KEY={cleaned}\n", encoding="utf-8")
    os.environ["TYPESAFE_API_KEY"] = cleaned


def _serialize_answer(answer: Any) -> dict[str, Any]:
    if hasattr(answer, "noul"):
        return {"type": "noul", "noul": float(answer.noul)}
    if hasattr(answer, "choice"):
        probs = getattr(answer, "probabilities", {}) or {}
        return {
            "type": "choice",
            "choice": answer.choice,
            "confidence": float(getattr(answer, "confidence", 0) or 0),
            "probabilities": {str(k): float(v) for k, v in dict(probs).items()},
        }
    if hasattr(answer, "score"):
        probs = getattr(answer, "probabilities", {}) or {}
        legend = getattr(answer, "legend", {}) or {}
        return {
            "type": "score",
            "score": float(answer.score),
            "confidence": float(getattr(answer, "confidence", 0) or 0),
            "legend": {str(k): str(v) for k, v in dict(legend).items()},
            "probabilities": {str(k): float(v) for k, v in dict(probs).items()},
        }
    return {"type": "unknown", "raw": str(answer)}


async def system_one(state: str, questions: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    key = resolve_key()
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not set")

    os.environ["TYPESAFE_API_KEY"] = key
    from typesafe_sdk import AsyncTypeSafeClient

    started = time.perf_counter()
    async with AsyncTypeSafeClient() as client:
        response = await client.system_one(
            state=state,
            questions=questions,
            model="jev-latest",
        )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    answers = {
        qid: _serialize_answer(response.answers[qid])
        for qid in questions
        if qid in response.answers
    }
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    meta = {
        "mode": "live",
        "model": getattr(response, "model", "jev-latest"),
        "elapsed_ms": elapsed_ms,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd": round(input_tokens / 1_000_000 * INPUT_PRICE_PER_MILLION, 8),
        },
    }
    return answers, meta
