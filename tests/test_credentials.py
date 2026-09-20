import json

import pytest

from jev_demo import credentials


def test_copy_uses_stdin_and_verifies_saved_key(monkeypatch):
    monkeypatch.setattr(credentials, "read_opencode_key", lambda: ("local-secret", "OpenCode auth.json (opencode-go)"))
    calls = []

    def op(args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ["item", "list"]:
            return 0, "[]", ""
        if args[:3] == ["item", "template", "get"]:
            return 0, json.dumps({"category": "API_CREDENTIAL", "fields": [
                {"id": "credential", "type": "CONCEALED", "value": ""},
                {"id": "notesPlain", "type": "STRING", "value": ""},
            ]}), ""
        if args[:2] == ["item", "create"]:
            body = json.loads(kwargs["input_text"])
            assert body["fields"][0]["value"] == "local-secret"
            assert body["title"] == "OpenCode"
            return 0, json.dumps({"id": "item-id", "vault": {"id": "vault-id"}}), ""
        assert args == ["read", "op://vault-id/item-id/credential"]
        return 0, "local-secret", ""

    monkeypatch.setattr(credentials, "_op", op)
    result = credentials.store_opencode_key("Private")
    assert result["action"] == "created"
    assert "local-secret" not in json.dumps(result)
    assert all("local-secret" not in repr(args) for args, _ in calls)


@pytest.mark.parametrize("stored,expected", [("local-secret", "already stored"), ("different-secret", None)])
def test_existing_item_is_not_overwritten(monkeypatch, stored, expected):
    monkeypatch.setattr(credentials, "read_opencode_key", lambda: ("local-secret", "OpenCode"))

    def op(args, **kwargs):
        if args[:2] == ["item", "list"]:
            return 0, '[{"id":"item-id","title":"OpenCode"}]', ""
        if args[:2] == ["item", "get"]:
            return 0, json.dumps({"id": "item-id", "vault": {"id": "vault-id"},
                "fields": [{"id": "credential", "value": stored}]}), ""
        assert args[0] == "read"
        return 0, stored, ""

    monkeypatch.setattr(credentials, "_op", op)
    if expected:
        assert credentials.store_opencode_key("Private")["action"] == expected
    else:
        with pytest.raises(RuntimeError, match="left unchanged"):
            credentials.store_opencode_key("Private")


def test_cli_error_does_not_echo_secret(monkeypatch):
    monkeypatch.setattr(credentials, "read_opencode_key", lambda: ("local-secret", "OpenCode"))
    monkeypatch.setattr(credentials, "_op", lambda *a, **kw: (1, "", "local-secret"))
    with pytest.raises(RuntimeError) as caught:
        credentials.store_opencode_key("Private")
    assert "local-secret" not in str(caught.value)
