import asyncio
import json
import subprocess
from types import SimpleNamespace

import httpx2
import pytest
import typesafe_sdk

from jev_demo import client

run_op = client._op


@pytest.mark.parametrize("provider,model,base_url,price", [
    ("opencode", None, "https://opencode.ai/zen/v1/systemone", 0),
    ("opencode", "jev-1.13", "https://opencode.ai/zen/v1/systemone", 0.042),
    ("opencode", "future-model", "https://opencode.ai/zen/v1/systemone", None),
    ("typesafe", None, "https://api.typesafe.ai/v1/systemone", 0.042),
])
def test_sdk_routes_key_model_and_cost_together(monkeypatch, provider, model, base_url, price):
    monkeypatch.setenv("JEV_PROVIDER", provider)
    monkeypatch.setenv("OPENCODE_API_KEY", "opencode-test-key")
    monkeypatch.setenv("TYPESAFE_API_KEY", "typesafe-test-key")
    # A stale SDK environment variable must not redirect a provider's credential.
    monkeypatch.setenv("TYPESAFE_BASE_URL", "https://wrong.invalid")
    if model:
        monkeypatch.setenv("JEV_MODEL", model)
    calls = []

    def respond(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert str(request.url) == base_url
        assert request.headers["Authorization"] == f"Bearer {provider}-test-key"
        assert payload["model"] == (model or client.PROVIDERS[provider]["model"])
        return httpx2.Response(200, json={
            "model": payload["model"],
            "answers": {"refund": {"type": "noul", "noul": 0.99}},
            "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
        })

    sdk = typesafe_sdk.AsyncTypeSafeClient
    monkeypatch.setattr(typesafe_sdk, "AsyncTypeSafeClient", lambda **kw: sdk(
        **kw, transport=httpx2.MockTransport(respond),
    ))
    answers, meta = asyncio.run(client.system_one(
        "Please refund this payment.",
        {"refund": {"type": "noul", "instructions": "Is a refund requested?"}},
    ))
    assert len(calls) == 1
    assert answers["refund"]["noul"] == 0.99
    assert meta["usage"]["usd"] == price
    assert client.os.environ["TYPESAFE_API_KEY"] == "typesafe-test-key"


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_cli_subprocess_is_portable_and_passes_secrets_on_stdin(monkeypatch, platform):
    monkeypatch.setattr(client, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(client, "_op_bin", lambda: "/test/op")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(kwargs["args"], 0, "{}", "")

    monkeypatch.setattr(client.subprocess, "run", run)
    assert run_op(["item", "create", "-"], input_text='{"credential":"test-secret"}')[0] == 0
    assert "test-secret" not in repr(calls[0]["args"])
    assert "test-secret" in calls[0]["input"]
    assert ("creationflags" in calls[0]) == (platform == "win32")


def test_home_path_is_used_without_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setattr(client.Path, "home", lambda: tmp_path)
    assert client.opencode_auth_path() == tmp_path / ".local" / "share" / "opencode" / "auth.json"
