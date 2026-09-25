#!/usr/bin/env python3
"""公式マニュアルへのリンク切れを検査する（search_manual と agent-guide が参照する URL）。

富岳のマニュアルは版上げで URL が変わる（例: 2026-09 に 1.52→1.53 となり search_manual が全件 404 になった）。
search_manual は取得失敗を「該当なし」と区別しにくいため、CI で定期的に検査して早期に気づけるようにする。
使い方: python tests/check_manual_links.py
"""
import json, os, re, sys, urllib.request as ur

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def reachable(url):
    req = ur.Request(url, method="HEAD", headers={"User-Agent": "fugaku-mcp-ci"})
    try:
        ur.urlopen(req, timeout=20)
        return True, ""
    except Exception as e:
        return False, str(getattr(e, "code", type(e).__name__))


urls = set()
idx = json.load(open(os.path.join(ROOT, "docs", "manual-pages.json"), encoding="utf-8"))
for pg in idx["pages"]:
    for lang in ("ja", "en"):
        urls.add(idx["guides"][pg["guide"]][lang] + pg["rel"])
for name in ("agent-guide.md", "agent-guide.en.md"):
    text = open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()
    urls |= set(re.findall(r"https://riken-rccs\.github\.io/[^\s)`]+", text))

bad = []
for u in sorted(urls):
    ok, why = reachable(u)
    if not ok:
        bad.append(f"  {why}  {u}")
print(f"マニュアルURL {len(urls)} 件を確認 / 到達できないもの {len(bad)} 件")
if bad:
    print("\n".join(bad))
    print("→ マニュアルの版が上がった可能性。docs/manual-pages.json と agent-guide の URL を更新すること。")
    sys.exit(1)
