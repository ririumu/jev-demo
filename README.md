# Jev Demo

[Jev](https://docs.typesafe.ai/introduction) は、文章を書くモデルではありません。状態（`state`）と、型のついた質問（`questions`）を JSON で渡すと、コードがそのまま分岐に使える値を JSON で返します。

大きな言語モデルは、人が読む文章を生成します。プログラムが判定を必要とするとき、その文章をまた構造化して読み戻す、という遠回りが生まれます。Jev はその遠回りをしません。質問も答えも JSON です。

このリポジトリは、そのやり取りを手元のブラウザで確認するための小さなデモです。API キーがなくても、同じ形の JSON をモックが返します。

## Jev が返すもの

たとえば、次のような JSON を送ります。

```json
{
  "state": "同じ金額が二回引き落とされています。今日中に返金してください。",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this message?",
      "criteria": {
        "billing": "Payments, invoices, refunds, subscriptions, charges",
        "technical": "Bugs, outages, integrations, login, product behavior"
      }
    },
    "refund_requested": {
      "type": "noul",
      "instructions": "Does the customer explicitly request a refund or chargeback reversal?"
    }
  }
}
```

返ってくるのは説明文ではなく、値です。

```json
{
  "department": {
    "type": "choice",
    "choice": "billing",
    "confidence": 0.91
  },
  "refund_requested": {
    "type": "noul",
    "noul": 0.94
  }
}
```

振り分けを決めるのは Jev ではなく、この値を読む Python です。質問と `if` は [recipes.py](src/jev_demo/recipes.py) に並んでいます。

```python
if refund >= 0.8 and department == "billing":
    # 請求チームへ自動で回す
```

質問の型は次の三つです。一度の呼び出しに混ぜて送れます。Jev はそれぞれを独立に、同じ `state` に対して評価します。

| 型 | 役割 | 返る値 |
|---|---|---|
| `choice` | 候補から一つ選ぶ | `choice`、`probabilities`、`confidence` |
| `score` | 基準に沿って採点する | `score`、`probabilities`、`confidence` |
| `noul` | 真偽を確率で返す | `noul`（0 から 1） |

画面では、送った `questions`、返ってきた `answers`、そしてコードが選んだ対応を並べて見られます。チャットのデモではありません。

## 動かし方

Python 3.11 以降が必要です。公開リポジトリは [ririumu/jev-demo](https://github.com/ririumu/jev-demo) です。

```sh
git clone https://github.com/ririumu/jev-demo.git
cd jev-demo
```

[uv](https://docs.astral.sh/uv/) がある場合:

```sh
uv sync
uv run jev-demo
```

pip を使う場合は、仮想環境を有効にしてから次を実行してください。

```sh
python -m pip install -e .
jev-demo
```

起動したら、ブラウザで http://127.0.0.1:8765 を開きます。左側でレシピを選び、サンプルを置いてから `Ask Jev` を押してください。入力欄の文章は自由に書き換えられます。

ポートを変えるときは `jev-demo --port 8766` です。キーを設定していても、画面の「モックで試す」で同じ JSON の形だけ確認できます。

[uvx](https://docs.astral.sh/uv/) なら、クローンせずに起動することもできます。

```sh
uvx --from "git+https://github.com/ririumu/jev-demo.git" jev-demo
```

## レシピ

| 画面 | 送る JSON と、コードが決めること |
|---|---|
| サポート振り分け | 担当部署・緊急度・返金の希望を一度に聞き、振り分け先を決める |
| ツール選択 | 次に使うツールを選び、引数は生成する側に残す |
| 差分ゲート | 秘密情報やリスクを調べ、止めるか通すかを決める |
| モデルの切り替え | いまの依頼が安く済むか、強いモデルへ上げるかを決める |

いずれも、判定用の JSON をコードの分岐へ渡すところまでの例です。

## API キー（任意）

キーがなくてもモックで動けます。実際の Jev に聞くときは、環境変数 `OPENCODE_API_KEY` か `JEV_KEY` を渡してください。既定の接続先は [OpenCode Zen の Jev](https://opencode.ai/docs/en/zen/#jev) で、モデルは `jev-1.13-free` です。

TypeSafe へ直接つなぐ場合は `JEV_PROVIDER=typesafe` と `TYPESAFE_API_KEY` を設定します。モデルを変える場合は `JEV_MODEL` です。

キーの値は、画面にも API にも出しません。

## 開発する

```sh
uv sync
uv run pytest
uv run jev-demo
```

[CI](.github/workflows/ci.yml) では Ubuntu・macOS・Windows 上でインストールと起動を確認します。テスト中の外部 API 呼び出しはモックです。

## License

[Apache License 2.0](LICENSE). Copyright 2026 ririumu.
