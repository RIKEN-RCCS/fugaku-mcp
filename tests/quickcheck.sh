#!/usr/bin/env bash
# 段0-1: 疎通 + 認証の切り分け (curl のみ・読み取り専用)
# 使い方:
#   X.509証明書がある場合:   ./quickcheck.sh cert /path/to/account.pem
#   アクセストークンがある場合: ./quickcheck.sh token "$ACCESS_TOKEN"
set -u
API="https://api.fugaku.r-ccs.riken.jp"
MODE="${1:-}"; CRED="${2:-}"
# RIKEN内プロキシが必要なら次行を設定: export https_proxy=http://xxx:port

echo "== 段0: 疎通 (TLSハンドシェイクまで) =="
curl -sS -o /dev/null -w "connect=%{http_connect} http=%{http_code} time=%{time_total}s\n" \
     --connect-timeout 10 "$API/status/" || echo "到達失敗(ネットワーク/プロキシ/DNSを疑う)"

echo; echo "== 段1: 認証つき GET /status/ (全マシン状態) =="
case "$MODE" in
  cert)  curl -sS --cert "$CRED" "$API/status/" ; echo ;;
  token) curl -sS -H "Authorization: Bearer $CRED" "$API/status/" ; echo ;;
  *) echo "引数: cert <pem> | token <access_token>"; exit 1 ;;
esac

echo; echo "== 段2(一部): computer の状態 / 実行中キュー (読み取りのみ) =="
AUTH=(); [ "$MODE" = cert ] && AUTH=(--cert "$CRED") || AUTH=(-H "Authorization: Bearer $CRED")
curl -sS "${AUTH[@]}" "$API/status/computer" ; echo
curl -sS "${AUTH[@]}" "$API/queue/computer/" ; echo
