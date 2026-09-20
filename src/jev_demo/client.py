"""TypeSafe key from 1Password, then one System One call. Nothing is written to disk."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import time
from typing import Any

INPUT_PRICE_PER_MILLION = 0.042
DEFAULT_ITEM = "TypeSafe"
_CACHE: dict[str, str] = {}


def _op_bin() -> str | None:
    found = shutil.which("op")
    if found:
        return found
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


def _op(args: list[str], timeout: float = 45) -> tuple[int, str, str]:
    binary = _op_bin()
    if not binary:
        return 127, "", "1Password CLI (op) is not installed"
    kwargs: dict[str, Any] = {
        "args": [binary, *args],
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "check": False,
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
    if ref.startswith("op://"):
        code, out, err = _op(["read", ref])
        if code == 0 and out:
            return out, ref
        return None, err or f"could not read {ref}"

    item = (os.environ.get("JEV_OP_ITEM") or DEFAULT_ITEM).strip()
    for field in ("credential", "password"):
        code, out, err = _op(["item", "get", item, "--reveal", "--fields", field])
        if code == 0 and out:
            return out, f"op item {item}/{field}"
        last_err = err
    return None, last_err or f"1Password item {item!r} has no credential/password field"


def resolve_key() -> str | None:
    if "secret" in _CACHE:
        return _CACHE["secret"]

    for name in ("TYPESAFE_API_KEY", "JEV_KEY", "JEV_API_KEY"):
        value = os.environ.get(name, "").strip()
        if not value:
            continue
        if value.startswith("op://"):
            code, out, err = _op(["read", value])
            if code == 0 and out:
                _CACHE["secret"] = out
                _CACHE["source"] = "1password"
                _CACHE["detail"] = value
                return out
            _CACHE["detail"] = err or f"could not read {value}"
            return None
        # Injected by `op run`. Not a file we wrote.
        _CACHE["secret"] = value
        _CACHE["source"] = "env"
        _CACHE["detail"] = name
        return value

    secret, detail = _from_onepassword()
    if secret:
        _CACHE["secret"] = secret
        _CACHE["source"] = "1password"
        _CACHE["detail"] = detail
        return secret
    _CACHE["detail"] = detail
    return None


def key_status() -> dict[str, Any]:
    present = resolve_key() is not None
    return {
        "present": present,
        "source": _CACHE.get("source") if present else None,
        "detail": _CACHE.get("detail"),
        "cli": _op_bin() is not None,
        "item": (os.environ.get("JEV_OP_ITEM") or DEFAULT_ITEM),
        "ref": (os.environ.get("JEV_OP_REF") or "").strip() or None,
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
        raise RuntimeError(_CACHE.get("detail") or "TypeSafe key not found in 1Password")

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
