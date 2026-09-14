#!/usr/bin/env python3
"""CI 用スモークテスト（富岳への通信なし・本物の証明書は不要）。

上流 SDK（mcp）の更新で「手元は動くのに新規インストールだけが壊れる」事故
（2026-08、v1.6.3 で対応）を早期に検知するためのもの。次を確認する:
  1. サーバが import でき、主要ツールがすべて登録される
  2. 実際に stdio で起動し、MCP クライアントから initialize → list_tools が通る
  3. ジョブスクリプトの改行が LF に正規化される（CRLF 混入対策）
  4. pjsub 応答から jobid を抽出できる（通常・ステップ・バルク）
  5. 監査ログがロケールに依存せず UTF-8 で書かれる

使い方: FUGAKU_CERT にダミーの自己署名 PEM（cert+key 結合）を指定して実行する。
  openssl req -x509 -newkey rsa:2048 -nodes -keyout k.pem -out c.pem -days 1 -subj "/CN=ci"
  cat c.pem k.pem > dummy.pem
  FUGAKU_CERT=dummy.pem python tests/ci_smoke.py
"""
import asyncio, importlib.metadata as md, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

if not os.environ.get("FUGAKU_CERT"):
    sys.exit("FUGAKU_CERT にダミー証明書のパスを指定してください（docstring 参照）")

# 通信を発生させない: 本人情報の自動検出（ctx）と更新チェックを固定値・無効で止める
os.environ.update({"FUGAKU_ACCOUNT": "ci", "FUGAKU_HOME": "/home/ci",
                   "FUGAKU_GROUP": "ci", "FUGAKU_NO_UPDATE_CHECK": "1"})
AUDIT = os.path.join(tempfile.mkdtemp(), "audit.jsonl")
os.environ["FUGAKU_AUDIT_LOG"] = AUDIT          # fugaku_policy は import 時に読むので先に設定

REQUIRED = {"cluster_status", "account_info", "fugaku_help", "search_manual", "check_update",
            "list_jobs", "run_command", "stage_in", "stage_out", "submit_job", "run_job",
            "fetch_result", "job_status", "cancel_job"}

failures = []


def check(name, ok, detail=""):
    print(f"  [{'OK' if ok else 'NG'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


print(f"mcp {md.version('mcp')} / Python {sys.version.split()[0]} / {sys.platform}")

import fugaku_mcp as fm          # noqa: E402
import fugaku_policy as policy   # noqa: E402

print(f"server class: {type(fm.mcp).__module__}")

# 1. ツール登録
names = {t.name for t in asyncio.run(fm.mcp.list_tools())}
missing = REQUIRED - names
check("主要ツールの登録", not missing,
      f"{len(names)}個" + (f" / 欠落: {sorted(missing)}" if missing else ""))


# 2. 実際に stdio で起動してハンドシェイク（クライアント側 API の互換性も同時に確認）
async def handshake():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable,
                                   args=[os.path.join(ROOT, "fugaku_mcp.py")],
                                   env=os.environ.copy())
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return {t.name for t in (await session.list_tools()).tools}

try:
    got = asyncio.run(asyncio.wait_for(handshake(), 90))
    check("stdio 経由の initialize → list_tools", REQUIRED <= got, f"{len(got)}個")
except Exception as e:
    check("stdio 経由の initialize → list_tools", False, f"{type(e).__name__}: {e}")


# 3・4. 投入処理（API を差し替えて通信せずに検証）
class FakeAPI:
    reply = "[INFO] PJM 0000 pjsub Job 12345 submitted."
    uploaded = b""

    def command(self, cmd, **kw):
        return 200, b'{"status":"OK","output":""}'

    def put_file(self, remote, data, **kw):
        FakeAPI.uploaded = data
        return 200, b'{"status":"OK"}'

    def submit(self, **kw):
        return 200, json.dumps({"status": "OK", "output": FakeAPI.reply}).encode()


real_api, fm.api = fm.api, FakeAPI()
try:
    crlf = "#!/bin/bash\r\necho a\r\nif true\r\nthen echo b\r\nfi\r\n"
    r = fm._submit_core(crlf, "citest", 1, "00:01:00", "small", "")
    check("CRLF → LF 正規化", b"\r" not in FakeAPI.uploaded and FakeAPI.uploaded.startswith(b"#!/bin/bash\n"))
    check("jobid 抽出（通常）", r.get("jobid") == "12345", str(r.get("jobid")))

    FakeAPI.reply = "[INFO] PJM 0000 pjsub Job 71080_0 submitted."
    r = fm._submit_core("echo x\n", "citest", 1, "00:01:00", "small", "--step")
    check("jobid 抽出（ステップジョブ）",
          r.get("jobid") == "71080" and r.get("subjobid") == "71080_0", f"{r.get('jobid')} / {r.get('subjobid')}")

    FakeAPI.reply = "[INFO] PJM 0000 pjsub Job 12345[3] submitted."
    r = fm._submit_core("echo x\n", "citest", 1, "00:01:00", "small", "--bulk")
    check("jobid 抽出（バルクジョブ）",
          r.get("jobid") == "12345" and r.get("subjobid") == "12345[3]", f"{r.get('jobid')} / {r.get('subjobid')}")
except Exception as e:
    check("投入処理", False, f"{type(e).__name__}: {e}")
finally:
    fm.api = real_api

# 5. 監査ログのエンコーディング（ロケールが UTF-8 でない環境でも壊れないこと）
text = "ls ~/実験データ ✅"
try:
    policy.audit("run_command", {"command": text})
    with open(AUDIT, "rb") as f:
        ok = text in f.read().decode("utf-8")
    check("監査ログが UTF-8（非ASCII・絵文字）", ok)
except Exception as e:
    check("監査ログが UTF-8（非ASCII・絵文字）", False, f"{type(e).__name__}: {e}")

if failures:
    print(f"\nFAILED: {failures}")
    sys.exit(1)
print("\nALL OK")
