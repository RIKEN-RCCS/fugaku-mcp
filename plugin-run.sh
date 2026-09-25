#!/usr/bin/env bash
# Claude Code プラグインからMCPサーバを起動するランチャ。
# 依存（requirements.txt）をプラグインのデータ領域の venv に導入し、サーバを exec する。
# CLAUDE_PLUGIN_ROOT / CLAUDE_PLUGIN_DATA は Claude Code が環境に渡す。
set -e
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
DATA="${CLAUDE_PLUGIN_DATA:-$ROOT/.data}"
VENV="$DATA/venv"
REQ="$ROOT/requirements.txt"
STAMP="$VENV/.requirements.cksum"   # 導入済み requirements の指紋（導入が成功したときだけ書く）

# 依存の導入・更新（pip等のノイズは stderr へ。stdout は MCP プロトコル専用）。
# 「venv があるか」ではなく「導入が完了したか」で判定する。こうしないと初回の pip が途中で失敗したとき
# venv だけが残り、以後の起動で導入がスキップされて永久に起動できなくなる。
# requirements.txt が変わった（プラグイン更新）ときも指紋の不一致で入れ直す。
want="$(cksum < "$REQ")"
if [ "$(cat "$STAMP" 2>/dev/null)" != "$want" ] || ! "$VENV/bin/python" -c "import mcp" >/dev/null 2>&1; then
  if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    echo "fugaku-mcp: Python 3.10 以上の python3 が必要です（現在: $(python3 --version 2>&1)）" >&2
    exit 1
  fi
  # venv が無い・壊れている（元の Python が消えた等）・古い Python で作られている場合は作り直す
  if ! "$VENV/bin/python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    python3 -m venv --clear "$VENV" >&2
  fi
  "$VENV/bin/pip" -q install -r "$REQ" >&2
  echo "$want" > "$STAMP"
fi

exec "$VENV/bin/python" "$ROOT/fugaku_mcp.py"
