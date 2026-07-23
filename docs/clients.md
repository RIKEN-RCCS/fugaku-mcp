日本語 | [English](clients.en.md)

# 各種MCPクライアントでの利用

`fugaku_mcp.py` は**標準的な MCP（stdio）サーバ**です。Claude Code 専用ではなく、**MCPに対応した
クライアントなら同じサーバをそのまま利用できます**（サーバ側の変更は不要）。クライアントごとに違うのは
**設定ファイルの書式だけ**です。

## どのクライアントでも指定する「3点」
| 項目 | 値 |
|---|---|
| **command** | venvのpython（絶対パス）例: `/path/to/fugaku-mcp/.venv/bin/python` |
| **args** | `fugaku_mcp.py` の絶対パス 例: `["/path/to/fugaku-mcp/fugaku_mcp.py"]` |
| **env** | `FUGAKU_CERT`（証明書パス）。任意で `FUGAKU_HOME` 等（[多ユーザー運用](multi-user.md) 参照）|

> HOME/アカウント/グループは起動時に自動検出されるため、最小設定は `FUGAKU_CERT` のみ。

## Claude Code
プロジェクト直下に `.mcp.json`（[QUICKSTART](../QUICKSTART.md) / `setup_user.sh` が生成）:
```json
{
  "mcpServers": {
    "fugaku": {
      "command": "/path/to/fugaku-mcp/.venv/bin/python",
      "args": ["/path/to/fugaku-mcp/fugaku_mcp.py"],
      "env": { "FUGAKU_CERT": "/path/to/<account>.pem" }
    }
  }
}
```

## OpenAI Codex CLI
`~/.codex/config.toml`（プロジェクト限定なら信頼済みプロジェクトの `.codex/config.toml`）に TOML で:
```toml
[mcp_servers.fugaku]
command = "/path/to/fugaku-mcp/.venv/bin/python"
args = ["/path/to/fugaku-mcp/fugaku_mcp.py"]
env = { FUGAKU_CERT = "/path/to/<account>.pem" }
```
または CLI で登録:
```bash
codex mcp add fugaku \
  --env FUGAKU_CERT=/path/to/<account>.pem \
  -- /path/to/fugaku-mcp/.venv/bin/python /path/to/fugaku-mcp/fugaku_mcp.py
```
詳細: [Codex 公式 MCP ドキュメント](https://developers.openai.com/codex/mcp)

検証済み（Codex CLI 0.142.3・gpt-5.5 で `cluster_status` を実行→富岳から `{"status":"OK","machine":"computer"}` 取得）。

> **承認について**: Codex は MCPツールの実行に承認を要求する。**Codexアプリ（対話）**では実行時の
> 承認ダイアログで許可すればよい。**非対話の `codex exec`** は既定が `approval: never` のため
> ツール呼び出しが自動キャンセルされる。承認ポリシーを設定する（テスト用途では
> `--dangerously-bypass-approvals-and-sandbox` で実行可能だが本番運用では非推奨）。
> Codex はクラウドのモデルを使うため、ツールの入出力はOpenAIへ送信される点に注意。

## vibe-local
[vibe-local](https://github.com/ochyai/vibe-local) はオフラインのAIコーディングエージェント（Python CLI・Ollama）で、
**設定書式は Claude Code と互換**（`mcpServers` 形式のJSON）。配置場所だけが異なります:
- グローバル: `~/.config/vibe-local/mcp.json`
- プロジェクト: `.vibe-local/mcp.json`

```json
{
  "mcpServers": {
    "fugaku": {
      "command": "/path/to/fugaku-mcp/.venv/bin/python",
      "args": ["/path/to/fugaku-mcp/fugaku_mcp.py"],
      "env": { "FUGAKU_CERT": "/path/to/<account>.pem" }
    }
  }
}
```
起動時にツールが自動登録されます（`mcp_fugaku_<ツール名>` の形で参照）。検証済み（`qwen3:8b` で
`cluster_status` 実行→富岳から `{"status":"OK","machine":"computer"}` 取得を確認）。

> **モデル選びのコツ**: ツールの実行には Ollama のネイティブ tool-calling に対応したモデルを使う
> （`qwen3:8b` で動作確認済み）。一部のモデル（例 `qwen3-coder:30b`）は tool 呼び出しを未解釈の
> テキスト形式で出力して実行されないことがある。長文・カンマ区切りのプロンプトは複数タスクに分割される
> ことがあるので、依頼は短い単文が無難。

> **プライバシー上の利点**: vibe-local は**ローカルLLM（Ollama）**で動くため、AIが読み取った内容
> （ファイル本文・ジョブ出力）が**クラウドへ送られません**。機微データを富岳でやり取りする場合に有利です。
> （Claude Code / Codex はクラウドのAIモデルへ送信されます）

## opencode
[opencode](https://opencode.ai) はOSSのターミナルAIコーディングエージェント。プロバイダを選べる
（Anthropic/OpenAI等のクラウド、またはOllamaのローカルLLM）。設定は `mcp` キー（**書式が独自**:
`command` は実行ファイルと引数を**1つの配列**にまとめ、環境変数のキー名は `environment`）:
- グローバル: `~/.config/opencode/opencode.json`
- プロジェクト: リポジトリ直下の `opencode.json`

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
      "environment": { "FUGAKU_CERT": "/path/to/<account>.pem" }
    }
  }
}
```
ツールは `fugaku_<ツール名>` の形で自動登録されます。

Ollama（ローカルLLM）で使う場合は `provider` も追記し、`opencode run -m ollama/<モデル名> "..."` で実行:
```json
{
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": { "baseURL": "http://localhost:11434/v1" },
      "models": { "gpt-oss:20b": { "name": "GPT-OSS 20B (local)" } }
    }
  }
}
```

検証済み（opencode 1.18.4 ＋ Ollama `gpt-oss:20b` / `qwen3:30b` の両方で `cluster_status` を実行→
富岳から `{"status":"OK","machine":"computer"}` 取得。ローカルLLM利用時は vibe-local と同様、
AIが読んだ内容はクラウドへ送られない）。

> **うまく動かないとき**: ローカルLLMでツール呼び出しが実行されない場合は、公式ドキュメントの推奨に従い
> Ollama側のコンテキスト長（`num_ctx`）を16k〜32k程度に増やす。モデルはネイティブtool-calling対応の
> ものを使う（`gpt-oss:20b`・`qwen3:30b` で動作確認済み）。

## その他のMCP対応クライアント（Cursor / VS Code / Cline など）
多くは Claude Code と同じ `mcpServers` 形式のJSON、または専用UIで `command`/`args`/`env` を登録します。
上の「3点」を各ツールの書式に合わせて記述してください。**stdio 起動・環境変数渡し**に対応していれば動作します。

## HTTP/SSE トランスポートが必要な場合
本サーバは既定で stdio です。クライアントが stdio を起動できず HTTP/SSE 接続のみ対応する場合は、
サーバを HTTP/SSE で起動する構成が別途必要です（FastMCP のトランスポート切替）。通常は stdio で十分です。

## 注意
- どのクライアントでも、安全策ポリシー（[security.md](security.md)）と監査は env 設定で同様に効きます。
- AIが読み取った内容はそのクライアントのAIモデルに送られます（プロバイダはクライアントに依存）。機微データの扱いに注意。
