#!/usr/bin/env bash
# 富岳MCP 多ユーザー向けオンボーディング補助（方式A: 各自ローカル）。
# PKCS#12証明書をPEM化し、疎通・本人情報を確認して、貼り付け用の .mcp.json を出力する。
#
# 使い方:  ./setup_user.sh <account>.p12 [出力先pem(省略時は同名.pem)]
set -euo pipefail
API="https://api.fugaku.r-ccs.riken.jp"
REPO="$(cd "$(dirname "$0")" && pwd)"
P12="${1:?使い方: ./setup_user.sh <account>.p12 [out.pem]}"
PEM="${2:-${P12%.p12}.pem}"

echo "== 1) PKCS#12 → PEM 変換（インポートパスフレーズを入力）=="
openssl pkcs12 -in "$P12" -nodes -out "$PEM"
chmod 600 "$PEM"
echo "   作成: $PEM (権限600)"

echo "== 2) 疎通・認証確認（GET /status/）=="
if ! curl -fsS --cert "$PEM" "$API/status/" >/dev/null; then
  echo "   失敗: 証明書/ネットワークを確認してください" >&2; exit 1
fi
echo "   OK: 認証成功"

echo "== 3) 本人情報の自動検出 =="
INFO=$(curl -fsS --cert "$PEM" -X POST "$API/command/computer/" \
  -d '{"command":"printf \"%s %s %s\" \"$(id -un)\" \"$HOME\" \"$(id -gn)\""}')
echo "   $INFO"

echo
echo "== 4) 貼り付け用 .mcp.json（プロジェクト直下に保存し Claude Code を完全再起動）=="
echo "   ※ HOME/グループは起動時に自動検出されるため、設定は証明書パスのみで可"
cat <<JSON
{
  "mcpServers": {
    "fugaku": {
      "command": "$REPO/.venv/bin/python",
      "args": ["$REPO/fugaku_mcp.py"],
      "env": {
        "FUGAKU_CERT": "$PEM"
      }
    }
  }
}
JSON
echo
echo "完了。venvが未作成なら: cd $REPO && python3 -m venv .venv && .venv/bin/pip install \"mcp[cli]\""
