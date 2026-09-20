from unittest.mock import patch
import json

import pytest

from jev_demo import client


def test_op_run_injected_env_is_used_without_cli(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "injected-from-op-run")
    with patch.object(client, "_op_bin", return_value=None):
        assert client.resolve_key() == "injected-from-op-run"
        status = client.key_status()
    assert status["present"] is True
    assert status["source"] == "env"


def test_op_reference_in_env_is_resolved(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "op://Private/OpenCode/credential")
    with patch.object(client, "_op", return_value=(0, "from-1password", "")):
        assert client.resolve_key() == "from-1password"
        status = client.key_status()
    assert status["source"] == "1password"
    assert status["detail"] == "op://Private/OpenCode/credential"


def test_item_lookup_uses_credential_field():
    def fake_op(args, timeout=45):
        if args[:2] == ["item", "get"] and "credential" in args:
            return 0, "item-secret", ""
        return 1, "", "nope"

    with patch.object(client, "_op", side_effect=fake_op), patch.object(
        client, "_op_bin", return_value="op"
    ):
        assert client.resolve_key() == "item-secret"
        assert client.key_status()["detail"] == "op item OpenCode/credential"


def test_missing_cli_stays_mock():
    with patch.object(client, "_op_bin", return_value=None), patch.object(
        client, "_op", return_value=(127, "", "1Password CLI (op) is not installed")
    ):
        assert client.resolve_key() is None
        status = client.key_status()
    assert status["present"] is False
    assert status["cli"] is False


def test_reload_clears_cache():
    client._CACHE["secret"] = "stale"
    client._CACHE["source"] = "env"
    client.reload_key()
    assert "secret" not in client._CACHE


def _write_auth(entries):
    path = client.opencode_auth_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(entries), encoding="utf-8")


@pytest.mark.parametrize("name", ["opencode", "opencode-go"])
def test_opencode_local_fallback_and_redacted_status(name):
    _write_auth({name: {"type": "api", "key": "local-secret"}})
    assert client.resolve_key() == "local-secret"
    status = client.key_status()
    assert status["source"] == "opencode"
    assert status["endpoint"] == "https://opencode.ai/zen/v1/systemone"
    assert status["model"] == "jev-1.13-free"
    assert "local-secret" not in json.dumps(status)


def test_onepassword_takes_priority_over_local_key(monkeypatch):
    _write_auth({"opencode-go": {"type": "api", "key": "local-secret"}})
    monkeypatch.setattr(client, "_op", lambda *a, **kw: (0, "vault-secret", ""))
    assert client.resolve_key() == "vault-secret"
    assert client.key_status()["source"] == "1password"


@pytest.mark.parametrize("variable,value", [
    ("JEV_OP_REF", "op://Private/Missing/credential"),
    ("JEV_OP_REF", "malformed-reference"),
    ("JEV_OP_ITEM", "Missing"),
    ("OPENCODE_API_KEY", "op://Private/Missing/credential"),
])
def test_explicit_reference_failure_does_not_fall_back(monkeypatch, variable, value):
    _write_auth({"opencode": {"type": "api", "key": "local-secret"}})
    monkeypatch.setenv(variable, value)
    assert client.resolve_key() is None


def test_provider_change_does_not_reuse_another_providers_key(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "opencode-secret")
    monkeypatch.setenv("TYPESAFE_API_KEY", "typesafe-secret")
    assert client.resolve_key() == "opencode-secret"
    monkeypatch.setenv("JEV_PROVIDER", "typesafe")
    assert client.resolve_key() == "typesafe-secret"
    assert client.key_status()["endpoint"] == "https://api.typesafe.ai/v1/systemone"


def test_typesafe_mode_never_uses_opencode_local_key(monkeypatch):
    _write_auth({"opencode": {"type": "api", "key": "local-secret"}})
    monkeypatch.setenv("JEV_PROVIDER", "typesafe")
    assert client.resolve_key() is None


@pytest.mark.parametrize("content", ["{", "[]", '{"opencode":{"type":"oauth","access":"unused"}}'])
def test_invalid_or_unsupported_auth_is_ignored(content):
    path = client.opencode_auth_path()
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    assert client.read_opencode_key()[0] is None
