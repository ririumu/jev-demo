"""Jev through OpenCode or TypeSafe, with credentials kept in memory."""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

INPUT_PRICE_PER_MILLION = 0.042
PROVIDERS = {
    "opencode": {
        "base_url": "https://opencode.ai/zen",
        "model": "jev-1.13-free",
        "item": "OpenCode",
        "key_env": "OPENCODE_API_KEY",
    },
    "typesafe": {
        "base_url": "https://api.typesafe.ai",
        "model": "jev-latest",
        "item": "TypeSafe",
        "key_env": "TYPESAFE_API_KEY",
    },
}
_CACHE: dict[str, str] = {}


def provider() -> str:
    name = (os.environ.get("JEV_PROVIDER") or "opencode").strip().lower()
    if name not in PROVIDERS:
        raise ValueError("JEV_PROVIDER must be opencode or typesafe")
    return name


def model_name() -> str:
    return (os.environ.get("JEV_MODEL") or "").strip() or PROVIDERS[provider()]["model"]


def item_name() -> str:
    return (os.environ.get("JEV_OP_ITEM") or "").strip() or PROVIDERS[provider()]["item"]


def _op_bin() -> str | None:
    found = shutil.which("op")
    if found:
        return found
    if sys.platform != "win32":
        return None
    home = os.path.expanduser("~")
    localapp = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(localapp, "Microsoft", "WinGet", "Links", "op.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "1Password CLI", "op.exe"),
        os.path.join(home, "AppData", "Local", "1Password CLI", "op.exe"),
        *glob.glob(os.path.join(localapp, "Microsoft", "WinGet", "Packages", "AgileBits.1Password.CLI*", "op.exe")),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _op(args: list[str], timeout: float = 45, *, input_text: str | None = None) -> tuple[int, str, str]:
    binary = _op_bin()
    if not binary:
        return 127, "", "1Password CLI (op) is not installed"
    kwargs: dict[str, Any] = {
        "args": [binary, *args],
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "check": False,
        "input": input_text,
        "encoding": "utf-8",
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(**kwargs)
    except FileNotFoundError:
        return 127, "", "1Password CLI (op) is not installed"
    except subprocess.TimeoutExpired:
        return 124, "", "1Password CLI timed out (unlock the desktop app and retry)"
    return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()


def _from_onepassword() -> tuple[str | None, str]:
    """Return (secret, detail). Secret stays in this process."""
    ref = (os.environ.get("JEV_OP_REF") or "").strip()
    if ref:
        if not ref.startswith("op://"):
            return None, "JEV_OP_REF must be a 1Password op:// reference"
        code, out, err = _op(["read", ref])
        if code == 0 and out:
            return out, ref
        return None, err or f"could not read {ref}"

    item = item_name()
    for field in ("credential", "password"):
        code, out, err = _op(["item", "get", item, "--reveal", "--fields", field])
        if code == 0 and out:
            return out, f"op item {item}/{field}"
        last_err = err
    return None, last_err or f"1Password item {item!r} has no credential/password field"


def opencode_auth_path() -> Path:
    root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / "opencode" / "auth.json"


def read_opencode_key() -> tuple[str | None, str]:
    try:
        auth = json.loads(opencode_auth_path().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, "OpenCode auth.json could not be read"
    if not isinstance(auth, dict):
        return None, "OpenCode auth.json is not an object"
    for name in ("opencode", "opencode-go"):
        entry = auth.get(name)
        if isinstance(entry, dict) and entry.get("type") == "api":
            key = entry.get("key")
            if isinstance(key, str) and key.strip():
                return key.strip(), f"OpenCode auth.json ({name})"
    return None, "OpenCode auth.json has no OpenCode API key"


def _remember(secret: str, source: str, detail: str) -> str:
    _CACHE.update(secret=secret, source=source, detail=detail, provider=provider())
    return secret


def resolve_key() -> str | None:
    name = provider()
    if _CACHE.get("provider") != name:
        _CACHE.clear()
    if "secret" in _CACHE:
        return _CACHE["secret"]

    for env_name in (PROVIDERS[name]["key_env"], "JEV_KEY", "JEV_API_KEY"):
        value = os.environ.get(env_name, "").strip()
        if not value:
            continue
        if value.startswith("op://"):
            code, out, err = _op(["read", value])
            if code == 0 and out:
                return _remember(out, "1password", value)
            _CACHE["detail"] = f"1Password could not read the reference in {env_name}"
            return None
        return _remember(value, "env", env_name)

    secret, detail = _from_onepassword()
    if secret:
        return _remember(secret, "1password", detail)
    # An explicit vault reference should fail visibly, rather than use a different key.
    explicit = any(os.environ.get(var, "").strip() for var in ("JEV_OP_REF", "JEV_OP_ITEM"))
    if name == "opencode" and not explicit:
        secret, detail = read_opencode_key()
        if secret:
            return _remember(secret, "opencode", detail)
    _CACHE["detail"] = (
        f"Could not read 1Password item {item_name()}; check op signin and JEV_OP_REF"
        if explicit or name == "typesafe" else detail
    )
    return None


def key_status() -> dict[str, Any]:
    present = resolve_key() is not None
    return {
        "present": present,
        "source": _CACHE.get("source") if present else None,
        "detail": _CACHE.get("detail"),
        "cli": _op_bin() is not None,
        "item": item_name(),
        "ref": (os.environ.get("JEV_OP_REF") or "").strip() or None,
        "provider": provider(),
        "model": model_name(),
        "endpoint": PROVIDERS[provider()]["base_url"] + "/v1/systemone",
    }


def reload_key() -> dict[str, Any]:
    _CACHE.clear()
    return key_status()


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
        raise RuntimeError(_CACHE.get("detail") or "Jev API key not found")

    from typesafe_sdk import AsyncTypeSafeClient

    started = time.perf_counter()
    selected_model = model_name()
    async with AsyncTypeSafeClient(api_key=key, base_url=PROVIDERS[provider()]["base_url"]) as client:
        response = await client.system_one(
            state=state,
            questions=questions,
            model=selected_model,
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
        "model": getattr(response, "model", selected_model),
        "provider": provider(),
        "elapsed_ms": elapsed_ms,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd": _estimated_cost(selected_model, input_tokens),
        },
    }
    return answers, meta


def _estimated_cost(model: str, input_tokens: int) -> float | None:
    if provider() == "opencode" and model == "jev-1.13-free":
        return 0.0
    if (provider(), model) in {("opencode", "jev-1.13"), ("typesafe", "jev-latest"), ("typesafe", "jev-1.13")}:
        return round(input_tokens / 1_000_000 * INPUT_PRICE_PER_MILLION, 8)
    return None
