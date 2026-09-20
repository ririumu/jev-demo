"""Each function is a Jev program: the questions dict, then Python ifs."""

from __future__ import annotations

from typing import Any

from jev_demo.client import system_one

YES = 0.8
NO = 0.2
CHOICE_CONFIDENCE = 0.45


async def ticket(state: str, *, mock: bool = False) -> dict[str, Any]:
    questions = {
        "department": {
            "type": "choice",
            "instructions": "Which team should handle this message?",
            "criteria": {
                "billing": "Payments, invoices, refunds, subscriptions, charges",
                "technical": "Bugs, outages, integrations, login, product behavior",
                "shipping": "Delivery status, delays, lost or damaged packages",
                "sales": "Pricing, upgrades, new accounts, plan questions",
                "other": "None of the options clearly fits",
            },
        },
        "frustration": {
            "type": "score",
            "instructions": "How frustrated does the customer appear?",
            "criteria": [
                "Calm, just stating facts",
                "Concerned or impatient but civil",
                "Very angry, strong language, or threatening to leave",
            ],
        },
        "is_urgent": {
            "type": "noul",
            "instructions": "Does the message convey time pressure or urgency?",
            "criteria": {
                "true": "Explicit deadline, ASAP, losing money, production down",
                "false": "No time pressure expressed",
            },
        },
        "wants_human": {
            "type": "noul",
            "instructions": "Is the customer asking to speak with a human agent?",
            "criteria": {
                "true": "Asks for a person, agent, or to stop talking to a bot",
                "false": "Does not request a human",
            },
        },
        "refund_requested": {
            "type": "noul",
            "instructions": "Does the customer explicitly request a refund or chargeback reversal?",
        },
    }

    if mock:
        blob = state.lower()
        refund = any(w in blob for w in ("返金", "refund", "charged twice", "二重", "引き落とし"))
        human = any(w in blob for w in ("人間", "担当者", "real person", "human", "agent"))
        urgent = any(w in blob for w in ("asap", "今日中", "losing", "3 days", "三回"))
        calm = any(w in blob for w in ("急ぎではありません", "教えてください", "how do i"))
        angry = any(w in blob for w in ("losing sales", "代わって", "angry", "もう十分", "三回"))
        if refund:
            department, department_confidence = "billing", 0.91
        elif any(w in blob for w in ("stripe", "integration", "ログイン", "パスワード", "bug", "crash")):
            department, department_confidence = "technical", 0.88
        elif any(w in blob for w in ("配送", "届", "shipping", "package")):
            department, department_confidence = "shipping", 0.8
        elif any(w in blob for w in ("料金", "upgrade", "plan")):
            department, department_confidence = "sales", 0.72
        else:
            department, department_confidence = "other", 0.4
        answers = {
            "department": {
                "type": "choice",
                "choice": department,
                "confidence": department_confidence,
                "probabilities": {
                    "billing": 0.85 if department == "billing" else 0.04,
                    "technical": 0.82 if department == "technical" else 0.05,
                    "shipping": 0.8 if department == "shipping" else 0.03,
                    "sales": 0.7 if department == "sales" else 0.04,
                    "other": 0.4 if department == "other" else 0.04,
                },
            },
            "frustration": {
                "type": "score",
                "score": 0.2 if calm else (1.85 if angry else (1.2 if urgent else 0.6)),
                "confidence": 0.86,
                "legend": {
                    "0": "Calm, just stating facts",
                    "1": "Concerned or impatient but civil",
                    "2": "Very angry, strong language, or threatening to leave",
                },
                "probabilities": {
                    "0": 0.82 if calm else 0.04,
                    "1": 0.86 if urgent and not angry and not calm else 0.08,
                    "2": 0.8 if angry else 0.04,
                },
            },
            "is_urgent": {"type": "noul", "noul": 0.96 if urgent else (0.08 if calm else 0.35)},
            "wants_human": {"type": "noul", "noul": 0.97 if human else 0.06},
            "refund_requested": {"type": "noul", "noul": 0.94 if refund else 0.05},
        }
        meta = {"mode": "mock", "model": "mock-jev", "elapsed_ms": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "usd": 0}}
    else:
        answers, meta = await system_one(state, questions)

    department = answers["department"]["choice"]
    confidence = answers["department"]["confidence"]
    frustration = answers["frustration"]["score"]
    urgent = answers["is_urgent"]["noul"]
    human = answers["wants_human"]["noul"]
    refund = answers["refund_requested"]["noul"]

    if NO < human < YES or (confidence < CHOICE_CONFIDENCE and department != "other"):
        policy = {
            "action": "review",
            "tone": "warn",
            "title": "人が見る",
            "detail": "判定が中間帯。自動振り分けせずレビューキューへ。",
        }
    elif human >= YES:
        policy = {
            "action": "human",
            "tone": "warn",
            "title": "有人対応",
            "detail": "顧客が人間を要求している。ボットには回さない。",
        }
    elif refund >= YES and department == "billing":
        policy = {
            "action": "billing-refund",
            "tone": "ok",
            "title": "請求チームへ（返金）",
            "detail": "返金要求が明確。billing に自動ルーティング。",
        }
    elif frustration >= 1.6 and urgent >= YES:
        policy = {
            "action": "priority",
            "tone": "warn",
            "title": f"優先キュー → {department}",
            "detail": "焦りと緊急が重なっている。部署は自動、優先度は上げる。",
        }
    else:
        policy = {
            "action": "auto",
            "tone": "ok",
            "title": f"自動振り分け → {department}",
            "detail": f"confidence {confidence:.2f}。コード側の閾値を超えたのでそのまま送る。",
        }

    return {"questions": questions, "answers": answers, "policy": policy, **meta}


async def tools(state: str, *, mock: bool = False) -> dict[str, Any]:
    questions = {
        "tool": {
            "type": "choice",
            "instructions": "Which tool should the coding agent call next?",
            "criteria": {
                "read": "Read a known file, usually to understand existing code or docs",
                "edit": "Change source or config that already exists",
                "bash": "Run a shell command: tests, git, install, build",
                "grep": "Search the repo for a symbol, string, or pattern",
                "none": "No tool is needed; a text reply is enough",
            },
        },
        "needs_tool": {
            "type": "noul",
            "instructions": "Does this turn require a tool call rather than a plain reply?",
            "criteria": {
                "true": "The agent must read, edit, search, or run something",
                "false": "A spoken answer or acknowledgement is enough",
            },
        },
    }

    if mock:
        blob = state.lower()
        if any(w in blob for w in ("十分", "thank", "don't", "しないで")):
            tool, needs, confidence = "none", 0.08, 0.9
        elif any(w in blob for w in ("テスト", "実行", "run ", "install", "git ")):
            tool, needs, confidence = "bash", 0.93, 0.82
        elif any(w in blob for w in ("探", "search", "todo", "grep", "一覧")):
            tool, needs, confidence = "grep", 0.9, 0.82
        elif any(w in blob for w in ("直して", "変えて", "edit", "修正")):
            tool, needs, confidence = "edit", 0.86, 0.82
        else:
            tool, needs, confidence = "read", 0.88, 0.82
        answers = {
            "tool": {
                "type": "choice",
                "choice": tool,
                "confidence": confidence,
                "probabilities": {
                    "read": 0.84 if tool == "read" else 0.04,
                    "edit": 0.84 if tool == "edit" else 0.04,
                    "bash": 0.84 if tool == "bash" else 0.04,
                    "grep": 0.84 if tool == "grep" else 0.04,
                    "none": 0.84 if tool == "none" else 0.04,
                },
            },
            "needs_tool": {"type": "noul", "noul": needs},
        }
        meta = {"mode": "mock", "model": "mock-jev", "elapsed_ms": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "usd": 0}}
    else:
        answers, meta = await system_one(state, questions)

    tool = answers["tool"]["choice"]
    confidence = answers["tool"]["confidence"]
    needs = answers["needs_tool"]["noul"]

    if needs <= NO or tool == "none":
        policy = {
            "action": "none",
            "tone": "ok",
            "title": "ツールなし",
            "detail": "Jev はテキスト返答で足りると判断。LLM に tool_choice=none。",
        }
    elif confidence < CHOICE_CONFIDENCE or NO < needs < YES:
        policy = {
            "action": "passthrough",
            "tone": "warn",
            "title": "パススルー",
            "detail": "自信が足りないのでリクエストは無改変。LLM が自分で選ぶ。",
        }
    else:
        policy = {
            "action": "forced",
            "tone": "ok",
            "title": f"forced → {tool}",
            "detail": "ツールは Jev、引数（パスやコマンド）は LLM。jev-gateway の forced モード。",
        }

    return {"questions": questions, "answers": answers, "policy": policy, **meta}


async def review(state: str, *, mock: bool = False) -> dict[str, Any]:
    questions = {
        "category": {
            "type": "choice",
            "instructions": "What kind of change is this hunk?",
            "criteria": {
                "bugfix": "Fixes incorrect behavior",
                "feature": "Adds user-visible behavior",
                "refactor": "Same behavior, different structure",
                "chore": "Docs, typos, formatting, comments",
                "other": "None of the options clearly fits",
            },
        },
        "risk": {
            "type": "score",
            "instructions": "How risky is shipping this hunk as-is?",
            "criteria": [
                "Cosmetic; no impact to functionality",
                "Behavior change with a limited blast radius",
                "Blocking: secrets, money movement, auth, or data loss",
            ],
        },
        "secret_leak": {
            "type": "noul",
            "instructions": "Does this hunk introduce a secret, API key, password, or live credential?",
            "criteria": {
                "true": "A real-looking key, token, or password is added in source",
                "false": "No credential is being committed",
            },
        },
        "tests_needed": {
            "type": "noul",
            "instructions": "Should this change include tests that are missing from the hunk?",
            "criteria": {
                "true": "New logic or money/auth behavior without tests",
                "false": "Docs, typo, or tests are already present",
            },
        },
    }

    if mock:
        blob = state.lower()
        secret = any(w in state for w in ("sk_live", "sk-", "api_key", "SECRET", "password"))
        tests_missing = "def " in state and "test" not in blob
        typo = any(w in blob for w in ("readme", "receive", "typo"))
        if secret:
            category, risk = "feature", 2.0
        elif typo:
            category, risk = "chore", 0.1
        elif tests_missing:
            category, risk = "feature", 1.35
        else:
            category, risk = "refactor", 0.9
        answers = {
            "category": {
                "type": "choice",
                "choice": category,
                "confidence": 0.84,
                "probabilities": {
                    "bugfix": 0.8 if category == "bugfix" else 0.05,
                    "feature": 0.8 if category == "feature" else 0.05,
                    "refactor": 0.8 if category == "refactor" else 0.05,
                    "chore": 0.8 if category == "chore" else 0.05,
                    "other": 0.8 if category == "other" else 0.05,
                },
            },
            "risk": {
                "type": "score",
                "score": risk,
                "confidence": 0.86,
                "legend": {
                    "0": "Cosmetic; no impact to functionality",
                    "1": "Behavior change with a limited blast radius",
                    "2": "Blocking: secrets, money movement, auth, or data loss",
                },
                "probabilities": {
                    "0": 0.8 if risk < 0.5 else 0.05,
                    "1": 0.8 if 0.5 <= risk < 1.6 else 0.05,
                    "2": 0.8 if risk >= 1.6 else 0.05,
                },
            },
            "secret_leak": {"type": "noul", "noul": 0.97 if secret else 0.04},
            "tests_needed": {
                "type": "noul",
                "noul": 0.9 if tests_missing and not secret else (0.2 if typo else 0.55),
            },
        }
        meta = {"mode": "mock", "model": "mock-jev", "elapsed_ms": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "usd": 0}}
    else:
        answers, meta = await system_one(state, questions)

    category = answers["category"]["choice"]
    risk = answers["risk"]["score"]
    secret = answers["secret_leak"]["noul"]
    tests = answers["tests_needed"]["noul"]

    if secret >= 0.7:
        policy = {
            "action": "block",
            "tone": "bad",
            "title": "ブロック：秘密情報",
            "detail": "キーやトークンがソースに入っている。マージしない。",
        }
    elif risk >= 1.6:
        policy = {
            "action": "changes",
            "tone": "warn",
            "title": "変更を要求",
            "detail": f"{category} だがリスクが高い。人が見てから。",
        }
    elif tests >= YES:
        policy = {
            "action": "tests",
            "tone": "warn",
            "title": "テストを足す",
            "detail": "ロジック変更なのにテストがハンクにない。",
        }
    else:
        policy = {
            "action": "approve",
            "tone": "ok",
            "title": f"通す（{category}）",
            "detail": "閾値以下。自動 approve してよい、という判定。",
        }

    return {"questions": questions, "answers": answers, "policy": policy, **meta}


async def model(state: str, *, mock: bool = False) -> dict[str, Any]:
    questions = {
        "tier": {
            "type": "choice",
            "instructions": "Which model tier should handle this coding turn?",
            "criteria": {
                "fast": "Typos, renames, color tweaks, summaries, trivial edits. Muse Spark is enough.",
                "balanced": "Normal feature or bug work with a clear shape. Mid-tier model.",
                "strong": "Hard debugging, design, races, security, or ambiguous architecture. Luna-class.",
            },
        },
        "is_hard": {
            "type": "noul",
            "instructions": "Is this turn hard enough that a cheap sticky parent should escalate to a stronger child model?",
            "criteria": {
                "true": "Design, races, security, unknown-cause bugs, large refactors",
                "false": "Mechanical or well-specified work the parent can finish",
            },
        },
    }

    if mock:
        blob = state.lower()
        hard = any(w in blob for w in ("設計", "レース", "認証", "security", "race", "architecture", "再設計"))
        trivial = any(w in blob for w in ("typo", "変数名", "色", "ボタン", "rename"))
        if hard:
            tier = "strong"
        elif trivial:
            tier = "fast"
        else:
            tier = "balanced"
        answers = {
            "tier": {
                "type": "choice",
                "choice": tier,
                "confidence": 0.87,
                "probabilities": {
                    "fast": 0.84 if tier == "fast" else 0.08,
                    "balanced": 0.84 if tier == "balanced" else 0.1,
                    "strong": 0.84 if tier == "strong" else 0.08,
                },
            },
            "is_hard": {"type": "noul", "noul": 0.92 if hard else (0.07 if trivial else 0.4)},
        }
        meta = {"mode": "mock", "model": "mock-jev", "elapsed_ms": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "usd": 0}}
    else:
        answers, meta = await system_one(state, questions)

    tier = answers["tier"]["choice"]
    confidence = answers["tier"]["confidence"]
    hard = answers["is_hard"]["noul"]
    label = {"fast": "Muse Spark", "balanced": "mid-tier", "strong": "Luna"}.get(tier, tier)

    if hard >= YES or tier == "strong":
        policy = {
            "action": "escalate",
            "tone": "warn",
            "title": "escalate → Luna",
            "detail": "親（Muse）は維持。強い子エージェントにだけ上げる。",
        }
    elif confidence < CHOICE_CONFIDENCE or NO < hard < YES:
        policy = {
            "action": "stay",
            "tone": "ok",
            "title": "stay（不確実）",
            "detail": "Jev が確信していないので親モデルのまま。fail-open。",
        }
    else:
        policy = {
            "action": "stay",
            "tone": "ok",
            "title": f"stay → {label}",
            "detail": "安い sticky 親のまま。キャッシュを温め続ける。",
        }

    return {"questions": questions, "answers": answers, "policy": policy, **meta}


RUNNERS = {
    "ticket": ticket,
    "tools": tools,
    "review": review,
    "model": model,
}

RECIPES = {
    "ticket": {
        "id": "ticket",
        "title": "サポート振り分け",
        "kicker": "Choice + Score + Noul",
        "blurb": "問い合わせを部署に振り、緊急度と人間対応の要否を同時に見る。Jev は判定だけ返し、ルーティングは Python が決める。",
        "placeholder": "顧客からのメールを貼る…",
        "samples": [
            {
                "label": "Stripe 連携が死んでいる",
                "text": "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP.",
            },
            {
                "label": "二重課金の返金",
                "text": "注文 A-104 で同じ金額が二回引き落とされています。重複分を今日中に返金してください。もう三回問い合わせています。",
            },
            {
                "label": "パスワードの聞き方",
                "text": "ログイン画面でパスワードを忘れた場合のリセット手順を教えてください。急ぎではありません。",
            },
            {
                "label": "人間と話したい",
                "text": "ボットにはもう十分です。担当者に代わってください。請求の件で三回メールしています。",
            },
        ],
    },
    "tools": {
        "id": "tools",
        "title": "コーディングエージェントのツール選択",
        "kicker": "OpenCode 風",
        "blurb": "jev-gateway がやっていることの縮小版。次に呼ぶツールを Jev が選び、引数は LLM に残す、という分担を体感する。",
        "placeholder": "エージェントへの指示を書く…",
        "samples": [
            {"label": "README を読む", "text": "このリポジトリの README を読んで、セットアップ手順を要約して。"},
            {"label": "テストを回す", "text": "失敗しているユニットテストを実行して、最初のエラーを見せて。"},
            {"label": "TODO を探す", "text": "src 以下の TODO コメントを全部探して一覧にして。"},
            {"label": "もう十分", "text": "ありがとう、それで十分です。変更はしないで。"},
        ],
    },
    "review": {
        "id": "review",
        "title": "差分ゲート",
        "kicker": "レビュー判定",
        "blurb": "パッチを読んでリスク・秘密情報・テスト不足を並列に見る。ブロックするか通すかは閾値を書いたコード側。",
        "placeholder": "git diff のハンクを貼る…",
        "samples": [
            {
                "label": "タイポ修正",
                "text": "--- a/README.md\n+++ b/README.md\n@@ -1,3 +1,3 @@\n-Recieve webhooks from Stripe.\n+Receive webhooks from Stripe.\n",
            },
            {
                "label": "キーが埋まっている",
                "text": "--- a/src/client.py\n+++ b/src/client.py\n@@ -3,6 +3,7 @@\n import os\n+\n+STRIPE_SECRET = \"EXAMPLE_DO_NOT_COMMIT\"\n def charge():\n     return os.environ[\"STRIPE_SECRET\"]\n",
            },
            {
                "label": "テストなしの機能",
                "text": "--- a/src/refunds.py\n+++ b/src/refunds.py\n@@ -10,0 +11,12 @@\n+def refund(order_id, amount):\n+    if amount > 10_000:\n+        return True\n+    api.post(\"/refunds\", json={\"order\": order_id, \"amount\": amount})\n+    return True\n",
            },
        ],
    },
    "model": {
        "id": "model",
        "title": "モデル階層ルーティング",
        "kicker": "OpenCode Go",
        "blurb": "opencode-jev-orchestrator の縮図。普段は Muse、難しいターンだけ Luna に上げる判定を Jev に任せる。",
        "placeholder": "今のターンの依頼を書く…",
        "samples": [
            {"label": "変数名", "text": "src/main.py の変数名 typo を直して。cnt を count にして。"},
            {
                "label": "認証の設計",
                "text": "既存のセッション Cookie 認証を、リプレイ耐性のあるトークンローテーション付きに再設計して。ログアウトと期限切れのレースも潰して。",
            },
            {"label": "色を変える", "text": "ヘッダーのボタンを青から黒に変えて。"},
        ],
    },
}


async def public_recipes() -> list[dict[str, Any]]:
    out = []
    for recipe_id, chrome in RECIPES.items():
        preview = await RUNNERS[recipe_id]("catalog-preview", mock=True)
        out.append(
            {
                **chrome,
                "questions": [
                    {
                        "id": key,
                        "type": spec["type"],
                        "instructions": spec["instructions"],
                        "criteria": spec.get("criteria"),
                    }
                    for key, spec in preview["questions"].items()
                ],
            }
        )
    return out


async def run(recipe_id: str, state: str, *, mock: bool) -> dict[str, Any]:
    return await RUNNERS[recipe_id](state, mock=mock)
