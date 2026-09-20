# Jev Demo

TypeSafe の [Jev](https://docs.typesafe.ai/introduction) は文章を書かない。Choice / Score / Noul の判定だけ返す。このアプリはその判定を Python の閾値で行動に変えるデモ。

```text
state + 複数の質問  →  Jev（並列判定）  →  確率
                                         ↓
                                   あなたのコードが決める
```

## 動かし方

```powershell
cd $env:USERPROFILE\dev\jev-demo
uv sync
uv run jev-demo
```

ブラウザで http://127.0.0.1:8765

キーがなくても **モック** で UI を一通り触れる。本番の Jev を使うときは TypeSafe のキーを画面に貼るか、`.env` に置く。

```powershell
copy .env.example .env
# TYPESAFE_API_KEY=... を書く
```

`~/.config/opencode/opencode-jev-orchestrator.key` も読む。

## レシピ

| 画面 | やっていること |
|---|---|
| サポート振り分け | 部署・緊急・有人・返金を一回で聞く |
| ツール選択 | OpenCode / jev-gateway の縮小版。ツールは Jev、引数は LLM |
| 差分ゲート | 秘密情報とリスクでマージを止める |
| モデル階層 | opencode-jev-orchestrator の縮図。Muse のまま / Luna に上げる |

Jev の出力トークンは課金されない。入力は公開価格で $0.042 / 百万トークン。

## License

[Apache License 2.0](LICENSE). Copyright 2026 ririumu.
