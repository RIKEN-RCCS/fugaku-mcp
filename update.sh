#!/usr/bin/env bash
# fugaku-mcp 更新スクリプト（git pull + 依存更新）。
# 使い方:  ./update.sh
set -e
cd "$(dirname "$0")"

echo "現在のバージョン: $(cat VERSION 2>/dev/null || echo '?')"

if [ ! -d .git ]; then
  echo "git クローンではないため自動更新できません。最新版を再取得してください:" >&2
  echo "  https://github.com/RIKEN-RCCS/fugaku-mcp" >&2
  exit 1
fi

# origin 乗っ取り対策: 公式リポかを確認してから取得する
origin=$(git remote get-url origin 2>/dev/null || echo "")
case "$origin" in
  *RIKEN-RCCS/fugaku-mcp*|*fumiyoshi-shoji/fugaku-mcp*) ;;   # 新オーナー / 旧オーナー(リダイレクト)
  *) echo "origin が公式リポではありません（更新中止）: $origin" >&2; exit 1 ;;
esac

echo "== fetch =="
git fetch --ff-only --tags origin
if [ -n "${FUGAKU_UPDATE_REF:-}" ]; then
  # 指定タグ/コミットに固定（サプライチェーン上、レビュー済みのrefに留めたい場合）
  echo "== checkout $FUGAKU_UPDATE_REF =="
  git checkout "$FUGAKU_UPDATE_REF"
else
  echo "== git pull (main, fast-forward only) =="
  git pull --ff-only
fi

echo "更新後のバージョン: $(cat VERSION 2>/dev/null || echo '?')"

# 依存（mcp）の更新（venvがあれば）
if [ -x .venv/bin/pip ]; then
  echo "== 依存パッケージ更新 =="
  .venv/bin/pip -q install -U mcp
fi

echo
echo "✅ 更新完了。反映するには MCPクライアント（Claude Code / Codex / vibe-local）を完全に再起動してください。"
