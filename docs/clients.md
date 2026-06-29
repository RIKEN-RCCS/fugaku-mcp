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
起動時にツールが自動登録されます（`mcp_fugaku_<ツール名>` の形で参照）。

> **プライバシー上の利点**: vibe-local は**ローカルLLM（Ollama）**で動くため、AIが読み取った内容
> （ファイル本文・ジョブ出力）が**クラウドへ送られません**。機微データを富岳でやり取りする場合に有利です。
> （Claude Code / Codex はクラウドのAIモデルへ送信されます）

## その他のMCP対応クライアント（Cursor / VS Code / Cline など）
多くは Claude Code と同じ `mcpServers` 形式のJSON、または専用UIで `command`/`args`/`env` を登録します。
上の「3点」を各ツールの書式に合わせて記述してください。**stdio 起動・環境変数渡し**に対応していれば動作します。

## HTTP/SSE トランスポートが必要な場合
本サーバは既定で stdio です。クライアントが stdio を起動できず HTTP/SSE 接続のみ対応する場合は、
サーバを HTTP/SSE で起動する構成が別途必要です（FastMCP のトランスポート切替）。通常は stdio で十分です。

## 注意
- どのクライアントでも、安全策ポリシー（[security.md](security.md)）と監査は env 設定で同様に効きます。
- AIが読み取った内容はそのクライアントのAIモデルに送られます（プロバイダはクライアントに依存）。機微データの扱いに注意。
