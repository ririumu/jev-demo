from unittest.mock import patch

from jev_demo import client


def setup_function() -> None:
    client._CACHE.clear()
    for name in ("TYPESAFE_API_KEY", "JEV_KEY", "JEV_API_KEY", "JEV_OP_REF", "JEV_OP_ITEM"):
        client.os.environ.pop(name, None)


def test_op_run_injected_env_is_used_without_cli():
    client.os.environ["TYPESAFE_API_KEY"] = "injected-from-op-run"
    with patch.object(client, "_op_bin", return_value=None):
        assert client.resolve_key() == "injected-from-op-run"
        status = client.key_status()
    assert status["present"] is True
    assert status["source"] == "env"


def test_op_reference_in_env_is_resolved():
    client.os.environ["TYPESAFE_API_KEY"] = "op://Private/TypeSafe/credential"
    with patch.object(client, "_op", return_value=(0, "from-1password", "")):
        assert client.resolve_key() == "from-1password"
        status = client.key_status()
    assert status["source"] == "1password"
    assert status["detail"] == "op://Private/TypeSafe/credential"


def test_item_lookup_uses_credential_field():
    def fake_op(args, timeout=45):
        if args[:2] == ["item", "get"] and "credential" in args:
            return 0, "item-secret", ""
        return 1, "", "nope"

    with patch.object(client, "_op", side_effect=fake_op), patch.object(
        client, "_op_bin", return_value="op"
    ):
        assert client.resolve_key() == "item-secret"
        assert client.key_status()["detail"] == "op item TypeSafe/credential"


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
