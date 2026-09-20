import pytest

from jev_demo import client


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    """Tests must never reach a developer's real keychain or OpenCode login."""
    client._CACHE.clear()
    for name in (
        "JEV_PROVIDER", "JEV_MODEL", "OPENCODE_API_KEY", "TYPESAFE_API_KEY",
        "TYPESAFE_BASE_URL", "JEV_KEY", "JEV_API_KEY", "JEV_OP_REF", "JEV_OP_ITEM",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(client, "_op", lambda *a, **kw: (127, "", "CLI unavailable in tests"))
    monkeypatch.setattr(client, "_op_bin", lambda: None)
    yield
    client._CACHE.clear()
