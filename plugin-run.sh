#!/usr/bin/env bash
# Claude Code プラグインからMCPサーバを起動するランチャ。
# 依存(mcp)をプラグインのデータ領域の venv に自動導入し、サーバを exec する。
# CLAUDE_PLUGIN_ROOT / CLAUDE_PLUGIN_DATA は Claude Code が環境に渡す。
set -e
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
DATA="${CLAUDE_PLUGIN_DATA:-$ROOT/.data}"
VENV="$DATA/venv"

# 初回のみ venv 作成 + mcp 導入（pip等のノイズは stderr へ。stdout は MCP プロトコル専用）
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" >&2
  "$VENV/bin/pip" -q install mcp >&2
fi

exec "$VENV/bin/python" "$ROOT/fugaku_mcp.py"
