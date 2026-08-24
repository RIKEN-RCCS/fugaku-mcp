日本語 | [English](QUICKSTART.en.md)

# クイックスタート — 富岳をAIアシスタントから使う

AIアシスタントに話しかけるだけで、富岳でのジョブ実行・ファイル操作・状態確認ができるようになります。
**所要 約5分**。プログラミングの知識は不要です。

**Claude Code / Codex / opencode** に対応しています（手順1・2は共通、手順3だけクライアントごとに異なります）。

## 0. 事前に用意するもの

- **富岳のアカウント** と **X.509クライアント証明書（`.p12` ファイル）**（HPCI/R-CCSのポータルで発行）
- **AIクライアント**のいずれか: [Claude Code](https://claude.com/claude-code)（デスクトップアプリ／CLI）、
  [Codex](https://developers.openai.com/codex)、[opencode](https://opencode.ai)
- **Python 3.10以上** と `git`、`openssl`（Mac/Linux標準。`python3 --version` で確認）
- OS: **macOS / Linux**。Windowsの場合は **WSL2** を使ってください（下記「Windowsで使う」参照）
- ネットワーク: **VPNは不要**（富岳WebAPIはインターネット公開。証明書で認証します）

## 1. 導入（初回のみ）

```bash
# ツールを取得して、専用のPython環境を用意
git clone https://github.com/RIKEN-RCCS/fugaku-mcp.git
cd fugaku-mcp
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]~=2.0"
```

> Python 3.14 で `mcp` の導入に失敗する場合は、3.12 で `python3.12 -m venv .venv` を使ってください。

## 2. 証明書を登録（初回のみ）

ダウンロードした `.p12` を渡すだけ。変換・疎通確認・設定ファイル生成まで自動です。

```bash
./setup_user.sh ~/Downloads/あなたの証明書.p12
```

- 途中で **証明書のパスフレーズ** を聞かれます（証明書発行時に決めたもの）。
- 成功すると、最後に **貼り付け用の `.mcp.json`** が表示されます。

## 3. AIクライアントに登録（初回のみ）

**お使いのクライアントの項だけ**を実施してください。どのクライアントでも設定するのは同じ**3点**です
（手順2の出力にすべて含まれています）。

| 設定項目 | 値 |
|---|---|
| 実行するPython | `<このリポジトリ>/.venv/bin/python` |
| 起動するスクリプト | `<このリポジトリ>/fugaku_mcp.py` |
| 環境変数 `FUGAKU_CERT` | 手順2で作られた `.pem` のパス |

> アカウント名・HOME・グループは**起動時に証明書から自動検出**されるので、設定は証明書のパスだけで済みます。

### Claude Code

1. 手順2で表示された `.mcp.json` の内容を、**Claude Codeで使うフォルダ（プロジェクト）の直下** に `.mcp.json` という名前で保存。
2. **Claude Code を完全に再起動**します。
   - Mac: アプリを最前面にして **⌘Q**（ウィンドウを閉じる✕だけでは不十分）→ 再度起動。
3. 起動時に「MCPサーバ `fugaku` を許可しますか？」と出たら **許可**。

> ターミナルの `claude` CLI をお使いなら、プラグインとして入れる方法もあります（`.mcp.json` の編集が不要）。
> ```bash
> claude plugin marketplace add RIKEN-RCCS/fugaku-mcp
> claude plugin install fugaku@fugaku-mcp
> ```
> この場合、証明書は `~/.fugaku/fugaku.pem` に置いてください。

### Codex

`~/.codex/config.toml` に追記します（**TOML形式**である点に注意）。

```toml
[mcp_servers.fugaku]
command = "/path/to/fugaku-mcp/.venv/bin/python"
args = ["/path/to/fugaku-mcp/fugaku_mcp.py"]
env = { FUGAKU_CERT = "/path/to/あなたの証明書.pem" }
```

コマンドで登録することもできます:

```bash
codex mcp add fugaku \
  --env FUGAKU_CERT=/path/to/あなたの証明書.pem \
  -- /path/to/fugaku-mcp/.venv/bin/python /path/to/fugaku-mcp/fugaku_mcp.py
```

登録後、Codexを再起動してください。

> **承認について**: Codexはツール実行のたびに承認を求めます。アプリでは表示されるダイアログで許可すればOKです。
> 非対話の `codex exec` は既定で承認を自動キャンセルするため、ツールが実行されません。

### opencode

`~/.config/opencode/opencode.json`（プロジェクト単位なら直下の `opencode.json`）に追記します。
**`command` は実行ファイルと引数を1つの配列にまとめ**、環境変数のキー名は `env` ではなく **`environment`** です。

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "fugaku": {
      "type": "local",
      "command": [
        "/path/to/fugaku-mcp/.venv/bin/python",
        "/path/to/fugaku-mcp/fugaku_mcp.py"
      ],
      "enabled": true,
      "environment": { "FUGAKU_CERT": "/path/to/あなたの証明書.pem" }
    }
  }
}
```

登録後、opencodeを再起動してください。ツールは `fugaku_<ツール名>` の形で使えるようになります。

> ローカルLLM（Ollama）と組み合わせれば、**読み取った内容がクラウドに出ません**。設定例は
> [docs/clients.md](docs/clients.md) を参照してください。

> **その他のクライアント**（vibe-local / Cursor / VS Code / Cline など）→ [docs/clients.md](docs/clients.md)

## Windowsで使う（WSL2）

導入スクリプト（`setup_user.sh` / `update.sh`）が bash・`openssl`・`curl` を前提としているため、
Windowsでは **WSL2（Windows Subsystem for Linux）** の中で動かしてください。WSL2内では
上記の手順1〜3がそのまま使えます。

```powershell
# PowerShell（管理者）で WSL2 + Ubuntu を導入し、再起動後に Ubuntu を起動
wsl --install -d Ubuntu
```

Ubuntu（WSL2）の中で:

```bash
sudo apt update && sudo apt install -y python3-venv git openssl
```

以降は**手順1から通常どおり**進めてください。Windows側で受け取った証明書は、WSL2からは
`/mnt/c/...` で参照できます。

```bash
# 例: Windowsのダウンロードフォルダにある証明書を使う
./setup_user.sh /mnt/c/Users/<Windowsのユーザー名>/Downloads/あなたの証明書.p12
```

> **注意点**
> - **証明書はWSL2側のホーム（`~/`）にコピーしてから使うことを推奨**します。`/mnt/c/...` は
>   パーミッションが期待どおりに効かず、`chmod 600` で秘密鍵を保護できません。
> - AIクライアントもWSL2側で動かしてください（Windows側のクライアントからWSL2内のMCPサーバは直接起動できません）。
> - 設定ファイルに書くパスは、すべて**WSL2内のパス**（`/home/<ユーザー名>/fugaku-mcp/.venv/bin/python` など）です。

> **ネイティブWindows（WSLなし）について**: MCPサーバ本体はPython標準ライブラリのみで書かれており、
> ネイティブWindowsでも動作する見込みですが、**現時点で実機検証をしていません**。
> 試す場合は venv のパスが `.venv\Scripts\python.exe` になる点と、`setup_user.sh` の代わりに
> 証明書変換（`openssl pkcs12 -in <証明書>.p12 -nodes -out <証明書>.pem`）を手動で行う必要がある点にご注意ください。
> うまくいった／いかなかった場合は [Issue](https://github.com/RIKEN-RCCS/fugaku-mcp/issues) でお知らせいただけると助かります。

## 4. 動作確認

新しい会話で、こう話しかけてください:

> 富岳の状態を確認して

`{"status":"OK","machine":"computer"}` のような応答が返れば成功です。続けて:

> 富岳での私のアカウント情報を見せて

→ あなたのアカウント名・HOME・グループが表示されます（設定ミスの確認に便利）。

## 5. 最初のタスク

> 富岳で `hostname` と `date` を実行して、結果を見せて

AIが裏でジョブを投入 → 完了を待つ → 結果を回収して見せてくれます。

## できること（話しかけ方の例）

| やりたいこと | 話しかけ方の例 |
|---|---|
| 稼働状態 | 「富岳の状態を見て」 |
| 自分のジョブ一覧 | 「実行中のジョブある？」「最近終わったジョブを見せて」 |
| ジョブ実行＋結果回収 | 「富岳で〇〇を実行して結果を見せて」 |
| ファイルを送る/取る | 「このファイルを富岳に置いて」「富岳の〇〇を取ってきて」 |
| 軽いコマンド | 「富岳で `ls ~/` して」 |

## 困ったとき

| 症状 | 対処 |
|---|---|
| `fugaku` のツールが出てこない | **クライアントを完全に再起動**（Claude Codeのデスクトップアプリは **⌘Q**。✕やウィンドウ閉じでは反映されません）。設定ファイルの場所とパスが正しいか確認 |
| Codexでツールが実行されない | 承認ダイアログで許可したか確認。`codex exec` は既定で自動キャンセルします |
| opencodeでツールが実行されない | `command` が**1つの配列**か、環境変数のキーが **`environment`** か確認 |
| 認証エラー / 状態が取れない | `setup_user.sh` をもう一度実行して証明書の疎通を確認。証明書の有効期限切れも確認 |
| 「証明書が見つからない」 | `.mcp.json` の `FUGAKU_CERT` のパスが正しいか確認 |
| ジョブが却下される | リソースグループ／課金グループの指定を確認（「〜のグループで投げて」と指定可）|

## 次のステップ
- **できること逆引き集（話しかけ方カタログ）** → [docs/usage-catalog.md](docs/usage-catalog.md)
- **FAQ・トラブルシューティング** → [docs/faq.md](docs/faq.md)
- 各クライアントの詳しい設定・その他のクライアント → [docs/clients.md](docs/clients.md)
- 多人数での運用・利用履歴の採取 → [docs/multi-user.md](docs/multi-user.md)
- 安全策（コマンド制限・資源上限・監査）→ [docs/security.md](docs/security.md)
- 仕組みの全体像 → [README](README.md)
