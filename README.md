# Jev Demo

TypeSafe の [Jev](https://docs.typesafe.ai/introduction) をローカルで試す Python アプリです。問い合わせ文やコードの差分を入力すると、Jev の判定と、Python の条件分岐が選んだ対応をブラウザで確認できます。

標準の接続先は [OpenCode Zen の Jev API](https://opencode.ai/docs/en/zen/#jev) です。OpenCode に保存した API キーをそのまま使えます。1Password に保管したキーにも対応しています。

Jev には、選択肢から選ぶ `Choice`、基準に沿って採点する `Score`、真偽の確率を返す `Noul` という質問の型があります。たとえばサポートの振り分けなら、担当部署や緊急度、返金の希望を一度の API 呼び出しで尋ね、返ってきた値を使って対応を決めます。質問と分岐のコードは [recipes.py](src/jev_demo/recipes.py) にあります。

## すぐ試す

Python 3.11 以降と Git を用意し、有効な仮想環境で実行します。Ubuntu・macOS・Windows で共通です。

```sh
python -m pip install "git+https://github.com/ririumu/jev-demo.git"
jev-demo
```

<details>
<summary>仮想環境を作る場合</summary>

Ubuntu / macOS:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Windows / PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

その後、上の `pip install` と `jev-demo` を実行します。Ubuntu で `venv` が入っていない場合は、`sudo apt install python3-venv` で追加できます。

</details>

[uv](https://docs.astral.sh/uv/) があるなら、一行で起動できます。

```sh
uvx --from "git+https://github.com/ririumu/jev-demo.git" jev-demo
```

起動したら、ブラウザで http://127.0.0.1:8765 を開きます。左側でレシピを選び、サンプルを押してから `Ask Jev` をクリックすると結果が出ます。入力欄の文章は自由に書き換えられます。

API キーが見つからないときは、自動でモックに切り替わります。モックは入力中のキーワードから結果を作るので、画面や分岐の動きを確認する用途に使えます。キーを設定済みでも「強制モック」で試せます。ポートを変える場合は `jev-demo --port 8766` のように指定してください。

## レシピ

| 画面 | 試せる判定 |
|---|---|
| サポート振り分け | 問い合わせの担当部署、緊急度、有人対応や返金の希望を調べ、振り分け先を決める |
| ツール選択 | `read`・`edit`・`bash`・`grep` などから次に使うツールを選ぶ。パスやコマンドなどの引数は LLM に任せる想定 |
| 差分ゲート | コード差分に秘密情報やリスクがあるかを調べ、マージを止めるか、修正やテストの追加を求めるかを決める |
| モデル階層 | 作業の難しさから、Muse Spark を続けるか、Luna に任せるかを決める |

いずれも、判定結果と対応方針を画面に表示するところまでのデモです。「ツール選択」は OpenCode / jev-gateway、「モデル階層」は opencode-jev-orchestrator の使い方を小さな例にしたものです。

## OpenCode のキーを使う

[OpenCode の `/connect`](https://opencode.ai/docs/providers/#credentials) で接続済みなら、デモがローカルの認証情報を読み込みます。`opencode` と `opencode-go` の API キーに対応しています。

キーは次の順に探します。

1. 環境変数 `OPENCODE_API_KEY`。`op run` で渡した値や `op://` 参照も使えます。
2. 1Password の `OpenCode` アイテム。`credential`、次に `password` フィールドを読みます。
3. OpenCode の `auth.json`。通常は `~/.local/share/opencode/auth.json`、`XDG_DATA_HOME` がある場合はその下の `opencode/auth.json` です。

画面には接続先・モデル・キーの取得元が出ます。同じ情報は `GET /api/status` から JSON で取得できます。キーの値は返しません。`JEV_KEY` と `JEV_API_KEY` も互換用の環境変数として使えます。

### 1Password にコピーする

[1Password CLI](https://www.1password.dev/cli/get-started) を入れ、`op --version` で確認します。デスクトップアプリの「設定 → 開発者」で **CLI 連携**を有効にしてください。このデモは `op` コマンドでキーを読み書きします。1Password SDK と MCP の連携設定は不要です。

`op vault list` が通れば接続できています。認証画面が出たら、1Password 側で承認してください。画面のない環境では、1Password CLI のサービスアカウントで認証し、下記の `JEV_OP_REF` で保管庫とアイテムを指定できます。

OpenCode に保存済みのキーをコピーするには、次を実行します。`Private` は自分の保管庫名に置き換えてください。

```sh
python -m jev_demo.credentials --vault Private
```

`OpenCode` という API Credential アイテムを作り、保存したキーを読み戻して確認します。キーは標準入力で CLI に渡します。同じキーが保存済みならそのまま使い、別のキーが入っていれば上書きせず終了します。

自分で登録する場合も、アイテム名を `OpenCode`、フィールドを `credential` にすれば読み込めます。起動済みの画面では「再読み込み」を押してください。

保管庫やアイテムを明示する場合は、`JEV_OP_REF` を使います。

Ubuntu / macOS:

```sh
export JEV_OP_REF="op://Private/OpenCode/credential"
jev-demo
```

Windows / PowerShell:

```powershell
$env:JEV_OP_REF = "op://Private/OpenCode/credential"
jev-demo
```

明示した参照を読めなかった場合は、そのエラーを表示します。参照の指定を外すと、通常の取得順に戻ります。

## モデルと料金

既定のモデルは `jev-1.13-free` です。OpenCode が期間限定で提供している無料モデルで、料金表示は $0 になります。有料モデルの `jev-1.13` を使う場合は `JEV_MODEL` に指定します。

```sh
export JEV_MODEL="jev-1.13"
jev-demo
```

```powershell
$env:JEV_MODEL = "jev-1.13"
jev-demo
```

`jev-1.13` の概算は入力 100 万トークンあたり $0.042、出力無料で計算しています（2026 年 9 月 21 日時点の [OpenCode の公開価格](https://opencode.ai/docs/en/zen/#pricing)）。未知のモデルは「料金未設定」と表示します。無料モデルの利用が終わった場合も、有料モデルへの切り替えは利用者が行います。

TypeSafe へ直接接続する場合は、`JEV_PROVIDER=typesafe` に設定してください。Bash では `export JEV_PROVIDER=typesafe`、PowerShell では `$env:JEV_PROVIDER = "typesafe"` です。この場合は `TYPESAFE_API_KEY` または 1Password の `TypeSafe` アイテムを読み、モデルは `jev-latest` になります。`JEV_MODEL` を設定済みなら、その指定が優先されます。

## 開発する

```sh
git clone https://github.com/ririumu/jev-demo.git
cd jev-demo
uv sync
uv run jev-demo
```

テストは `uv run pytest` で実行します。[CI](.github/workflows/ci.yml) では Ubuntu・macOS・Windows 上で Git URL からインストールし、テストとインストール後の起動確認を行います。テスト中の API 呼び出しと 1Password 操作はモックです。

## License

[Apache License 2.0](LICENSE). Copyright 2026 ririumu.
