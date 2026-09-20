import asyncio

from jev_demo.app import DecideBody, decide_route, recipes


def test_decide_returns_the_questions_json():
    result = asyncio.run(decide_route(DecideBody(
        recipe="ticket",
        text="注文 A-104 の重複分を今日中に返金してください。",
        mock=True,
    )))
    assert result["questions"]["department"]["type"] == "choice"
    assert result["answers"]["refund_requested"]["noul"] >= 0.8
    assert result["policy"]["action"] == "billing-refund"


def test_catalog_questions_are_the_jev_object():
    payload = asyncio.run(recipes())
    ticket = next(item for item in payload["recipes"] if item["id"] == "ticket")
    assert ticket["questions"]["department"]["type"] == "choice"
    assert "criteria" in ticket["questions"]["department"]
    assert not isinstance(ticket["questions"], list)
