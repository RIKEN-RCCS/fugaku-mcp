#!/usr/bin/env python3
"""富岳上に集約された MCP 監査ログ（<remote>/<account>.jsonl）を集計してレポートする。

方式A（各自ローカル実行）でも、各MCPサーバが FUGAKU_AUDIT_REMOTE を設定していれば
利用履歴は富岳上の1ディレクトリに集まる。本スクリプトはそれを読み出して集計する。

使い方:
  python3 audit_report.py --cert /path/<account>.pem --remote /vol0004/<group>/<proj>/mcp-audit
  オプション: --since 2026-06-01  --json
"""
import argparse, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fugaku_api import FugakuAPI, norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cert", required=True)
    ap.add_argument("--remote", required=True, help="富岳上の監査ディレクトリ")
    ap.add_argument("--since", default="", help="YYYY-MM-DD 以降のみ集計")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    api = FugakuAPI(a.cert)

    d = a.remote.rstrip("/")
    # 全アカウントの .jsonl をまとめて取得（各行に account フィールドあり）
    res = norm(api.command(f"cat {d}/*.jsonl 2>/dev/null"))
    raw = str(res.get("output", ""))
    recs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if a.since and str(r.get("ts", "")) < a.since:
            continue
        recs.append(r)

    if not recs:
        print("監査レコードなし（パス・--since・各サーバのFUGAKU_AUDIT_REMOTE設定を確認）")
        return

    by_acct, by_tool, by_day, violations = {}, {}, {}, 0
    for r in recs:
        by_acct[r.get("account")] = by_acct.get(r.get("account"), 0) + 1
        by_tool[r.get("tool")] = by_tool.get(r.get("tool"), 0) + 1
        by_day[str(r.get("ts", ""))[:10]] = by_day.get(str(r.get("ts", ""))[:10], 0) + 1
        if r.get("ok") is False:
            violations += 1

    if a.json:
        print(json.dumps({"total": len(recs), "by_account": by_acct, "by_tool": by_tool,
                          "by_day": by_day, "policy_violations": violations},
                         ensure_ascii=False, indent=2))
        return

    def tbl(title, d2):
        print(f"\n== {title} ==")
        for k, v in sorted(d2.items(), key=lambda x: -x[1]):
            print(f"  {str(k):24} {v}")

    print(f"総操作数: {len(recs)}  / ポリシー違反(ok=false): {violations}")
    tbl("ユーザー別", by_acct)
    tbl("ツール別", by_tool)
    tbl("日別", by_day)


if __name__ == "__main__":
    main()
