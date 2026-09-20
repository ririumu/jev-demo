import asyncio

from jev_demo.recipes import run


def _run(recipe: str, text: str) -> dict:
    return asyncio.run(run(recipe, text, mock=True))


def test_refund_ticket_routes_to_billing():
    result = _run("ticket", "注文 A-104 の重複分を今日中に返金してください。")
    assert result["policy"]["action"] == "billing-refund"
    assert result["questions"]["department"]["type"] == "choice"
    assert result["questions"]["is_urgent"]["type"] == "noul"


def test_human_request_escalates():
    result = _run("ticket", "担当者に代わってください。人間と話したい。")
    assert result["policy"]["action"] == "human"


def test_thanks_needs_no_tool():
    result = _run("tools", "ありがとう、それで十分です。変更はしないで。")
    assert result["policy"]["action"] == "none"


def test_secret_hunk_is_blocked():
    result = _run("review", 'STRIPE_SECRET = "EXAMPLE_DO_NOT_COMMIT"')
    assert result["policy"]["action"] == "block"


def test_hard_turn_escalates():
    result = _run("model", "認証をトークンローテーション付きに再設計して。レースも潰して。")
    assert result["policy"]["action"] == "escalate"
    assert "Luna" not in result["policy"]["title"]
    assert "Muse" not in result["policy"]["detail"]


def test_typo_stays_on_fast_parent():
    result = _run("model", "src/main.py の変数名 typo を直して。")
    assert result["policy"]["action"] == "stay"
