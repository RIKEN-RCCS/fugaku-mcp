#!/usr/bin/env python3
"""CI 用スモークテスト（富岳への通信なし・本物の証明書は不要）。

上流 SDK（mcp）の更新で「手元は動くのに新規インストールだけが壊れる」事故
（2026-08、v1.6.3 で対応）を早期に検知するためのもの。次を確認する:
  1. サーバが import でき、主要ツールがすべて登録される
  2. 実際に stdio で起動し、MCP クライアントから initialize → list_tools が通る
  3. ジョブスクリプトの改行が LF に正規化される（CRLF 混入対策）
  4. pjsub 応答から jobid を抽出できる（通常・ステップ・バルク）
  5. 監査ログがロケールに依存せず UTF-8 で書かれる
  6〜14. 2026-09 のレビュー指摘の回帰防止（extra_qopt/#PJM による資源上限の迂回拒否、タイムアウト復旧の
     完全一致、結果ファイルの事前削除、ジョブ名検証と自動命名、stage_in の空指定拒否、手元の隠しパス拒否、
     rm の表記ゆれ、HOME 検出失敗の明示エラー、導入方法に応じた更新手順）

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
    submit_http = 200            # None でタイムアウトを模擬
    queue_jobs = []              # タイムアウト復旧時にキューが返すジョブ
    uploaded = b""
    events = []                  # 呼び出し順の記録

    def command(self, cmd, **kw):
        FakeAPI.events.append(("command", cmd))
        return 200, b'{"status":"OK","output":""}'

    def put_file(self, remote, data, **kw):
        FakeAPI.events.append(("upload", remote))
        FakeAPI.uploaded = data
        return 200, b'{"status":"OK"}'

    def submit(self, **kw):
        FakeAPI.events.append(("submit", kw.get("qopt")))
        if FakeAPI.submit_http is None:
            return None, b"TimeoutError: timed out"
        return 200, json.dumps({"status": "OK", "output": FakeAPI.reply}).encode()

    def queue(self, **kw):
        return 200, json.dumps({"status": "OK", "output": FakeAPI.queue_jobs}).encode()


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
    FakeAPI.reply = "[INFO] PJM 0000 pjsub Job 12345 submitted."

    # 6. extra_qopt / #PJM による資源上限の迂回を拒否すること
    def rejected(**kw):
        try:
            fm._submit_core(kw.pop("script", "echo x\n"), "citest", 1, "00:10:00", "small", kw.pop("extra", ""))
            return False
        except policy.PolicyError:
            return True
    check("extra_qopt の資源・課金グループ上書きを拒否",
          all(rejected(extra=q) for q in ['-L "node=384"', '--rsc-list=elapse=24:00:00',
                                          '-L "rscgrp=large"', '-g other', '--gname=other', '-N x']))
    check("#PJM 指示子の食い違いを拒否・一致は許可",
          rejected(script='#PJM -L "node=384"\necho x\n')
          and not rejected(script='#PJM -L "node=1"\n#PJM -L "elapse=10:00"\necho x\n'))
    check("無関係な extra_qopt は通す",
          not rejected(extra='--mpi "proc=8" -x PJM_LLIO_GFSCACHE=/vol0004 -S -L "freq=2200"'))

    # 7. 投入タイムアウト時の復旧はジョブ名の完全一致（run1 が run10 を拾わない）
    FakeAPI.submit_http, FakeAPI.queue_jobs = None, [{"name": "run10", "jobid": "111"},
                                                     {"name": "run1", "jobid": "222"}]
    fm.time.sleep, real_sleep = (lambda s: None), fm.time.sleep
    try:
        r = fm._submit_core("echo x\n", "run1", 1, "00:01:00", "small", "")
    finally:
        fm.time.sleep, FakeAPI.submit_http, FakeAPI.queue_jobs = real_sleep, 200, []
    check("タイムアウト復旧がジョブ名の完全一致", r.get("jobid") == "222", str(r.get("jobid")))

    # 8. run_job の結果ファイルを投入直前に消す（前回分を今回の結果と誤認しない）
    FakeAPI.events = []
    fm._submit_core("echo x\n", "citest", 1, "00:01:00", "small", "", clear_path="/home/ci/mcp-jobs/citest.result")
    kinds = [e[0] for e in FakeAPI.events]
    rm_at = next((i for i, e in enumerate(FakeAPI.events) if e == ("command", "rm -f /home/ci/mcp-jobs/citest.result")), -1)
    check("結果ファイルを投入直前に削除", 0 <= rm_at < kinds.index("submit") and kinds.index("upload") < rm_at)
except Exception as e:
    check("投入処理", False, f"{type(e).__name__}: {e}")
finally:
    fm.api = real_api


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
        return False
    except exc:
        return True


# 9. ジョブ名の検証（fetch_result の '..' でジョブ置き場の外を読ませない）と自動命名
check("fetch_result の不正な name を拒否", raises(ValueError, fm.fetch_result, "../../../vol0004/x"))
n1, n2 = fm._auto_name(), fm._auto_name()
check("name 省略時の自動名が一意かつ有効", n1 != n2 and not raises(ValueError, fm._check_name, n1), n1)

# 10. stage_in: content も local_path も無い呼び出しで既存ファイルを空にしない
check("stage_in の内容未指定を拒否", raises(ValueError, fm.stage_in, "/home/ci/x"))

# 11. 手元の隠しファイル（鍵・設定）への読み書きを拒否
check("手元の隠しパスへの保存を拒否",
      raises(policy.PolicyError, fm.stage_out, "/home/ci/x", local_path=os.path.join(os.path.expanduser("~"), ".ssh", "k")))

# 12. rm の再帰＋強制削除を表記ゆれ込みで拒否（-rf 以外は通す）
check("rm -Rf / -r -f / --recursive --force を拒否",
      all(raises(policy.PolicyError, policy.check_command, c)
          for c in ["rm -Rf *", "rm -r -f *", "rm -fR data", "rm --recursive --force data"])
      and not raises(policy.PolicyError, policy.check_command, "rm -f a.txt"))

# 13. 本人情報の自動検出に失敗したら "None/mcp-jobs" で続行せず明示エラー
saved = dict(fm._ctx)
fm._ctx.update(home=None)
real_api, fm.api = fm.api, FakeAPI()
try:
    check("HOME 検出失敗で明示エラー", raises(RuntimeError, fm.jobdir))
finally:
    fm.api = real_api
    fm._ctx.update(saved)

# 14. 更新手順が導入方法に合っていること（プラグインのキャッシュは git クローンではない）
import fugaku_update as updater   # noqa: E402
real_here, updater.HERE = updater.HERE, os.path.join(os.sep, "x", ".claude", "plugins", "cache", "fugaku")
try:
    check("プラグイン導入時の更新手順", "claude plugin update" in updater.HOW_TO_UPDATE[updater.install_kind()])
finally:
    updater.HERE = real_here

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
