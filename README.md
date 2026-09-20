# Jev Demo

TypeSafe の [Jev](https://docs.typesafe.ai/introduction) をローカルで試す Python アプリです。問い合わせ文やコードの差分を入力すると、Jev の判定と、それを受けて Python の条件分岐が選んだ対応をブラウザで確認できます。

Jev には、選択肢から選ぶ `Choice`、基準に沿って採点する `Score`、真偽の確率を返す `Noul` という質問の型があります。たとえばサポートの振り分けなら、担当部署や緊急度、返金の希望を一度の API 呼び出しで尋ね、返ってきた値を使って対応を決めます。質問と分岐のコードは [recipes.py](src/jev_demo/recipes.py) にあります。

## 動かし方

Python 3.11 以降と uv を使います。以下は PowerShell での例です。

```powershell
git clone https://github.com/ririumu/jev-demo.git
cd jev-demo
uv sync
uv run jev-demo
```

起動したら、ブラウザで http://127.0.0.1:8765 を開きます。左側でレシピを選び、サンプルを押してから `Ask Jev` をクリックすると結果が出ます。入力欄の文章は自由に書き換えられます。

API キーが見つからないときは、自動でモックに切り替わります。モックは入力中のキーワードから結果を作るので、画面や分岐の動きを確認する用途に使えます。キーを設定済みでも、画面の「強制モック」にチェックを入れると試せます。

## レシピ

| 画面 | 試せる判定 |
|---|---|
| サポート振り分け | 問い合わせの担当部署、緊急度、有人対応や返金の希望を調べ、振り分け先を決める |
| ツール選択 | `read`・`edit`・`bash`・`grep` などから次に使うツールを選ぶ。パスやコマンドなどの引数は LLM に任せる想定 |
| 差分ゲート | コード差分に秘密情報やリスクがあるかを調べ、マージを止めるか、修正やテストの追加を求めるかを決める |
| モデル階層 | 作業の難しさから、Muse Spark を続けるか、Luna に任せるかを決める |

いずれも、判定結果と対応方針を画面に表示するところまでのデモです。「ツール選択」は OpenCode / jev-gateway、「モデル階層」は opencode-jev-orchestrator の使い方を小さな例にしたものです。

## Jev API を使う

API キーは 1Password から読み込みます。`.env` ファイルの用意は不要です。

1. [1Password CLI](https://developer.1password.com/docs/cli/get-started/) をインストールします。
2. 1Password のデスクトップアプリを開き、Settings → Developer → Integrate with 1Password CLI を有効にします。
3. `TypeSafe` という名前のアイテムを作り、API キーを保存します。API Credential なら `credential`、Login なら `password` フィールドを使います。
4. `uv run jev-demo` で起動します。起動済みなら、画面の「再読み込み」を押すとキーを読み直せます。

保存先を指定する場合は、`JEV_OP_REF` に 1Password の参照を設定します。次の例では、保管庫名が `Private`、アイテム名が `TypeSafe` です。手元の名前とフィールドに合わせて変更してください。

```powershell
$env:JEV_OP_REF = "op://Private/TypeSafe/credential"
uv run jev-demo
```

`op run` から環境変数として渡す方法も使えます。

```powershell
$env:TYPESAFE_API_KEY = "op://Private/TypeSafe/credential"
op run -- uv run jev-demo
```

画面の料金表示は、入力 100 万トークンあたり $0.042、出力無料として計算しています。これは [TypeSafe の公開価格](https://typesafe.ai/blog/introducing-system-one-models-and-jev) に基づく、2026 年 9 月 21 日時点の設定です。

## License

[Apache License 2.0](LICENSE). Copyright 2026 ririumu.
