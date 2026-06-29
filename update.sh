#!/usr/bin/env bash
# fugaku-mcp 更新スクリプト（git pull + 依存更新）。
# 使い方:  ./update.sh
set -e
cd "$(dirname "$0")"

echo "現在のバージョン: $(cat VERSION 2>/dev/null || echo '?')"

if [ ! -d .git ]; then
  echo "git クローンではないため自動更新できません。最新版を再取得してください:" >&2
  echo "  https://github.com/fumiyoshi-shoji/fugaku-mcp" >&2
  exit 1
fi

echo "== git pull =="
git pull --ff-only

echo "更新後のバージョン: $(cat VERSION 2>/dev/null || echo '?')"

# 依存（mcp）の更新（venvがあれば）
if [ -x .venv/bin/pip ]; then
  echo "== 依存パッケージ更新 =="
  .venv/bin/pip -q install -U mcp
fi

echo
echo "✅ 更新完了。反映するには MCPクライアント（Claude Code / Codex / vibe-local）を完全に再起動してください。"
