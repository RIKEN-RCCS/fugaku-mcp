#!/usr/bin/env python3
"""Fugaku WebAPI 段階的スモークテスト（X.509証明書版・標準ライブラリのみ）。

外部依存なし(urllib+ssl)。account.pem(cert+key結合) で直接RESTを叩く。
FugakuAPI クラスはそのまま将来のMCPサーバの土台に流用できる。

準備:  openssl pkcs12 -in account.p12 -nodes -out account.pem
使い方:
  python3 cert_smoke_test.py --cert <account>.pem --home /home/<account> --max-stage 2
  ...問題なければ --max-stage を 3→4→5 と上げる
  --keep 後始末をしない / --proxy http://host:port / --insecure TLS検証無効
"""
import argparse, json, re, ssl, sys, time
import urllib.request as ur
import urllib.parse as up
from urllib.error import HTTPError, URLError

API = "https://api.fugaku.r-ccs.riken.jp"
MACHINE = "computer"
TERMINAL = {"EXT", "CCL", "ERR", "RJT"}          # ジョブ終端ステータス


class FugakuAPI:
    def __init__(self, cert, proxy=None, verify=True, timeout=60):
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(certfile=cert)        # cert+key 結合PEM
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        handlers = [ur.HTTPSHandler(context=ctx)]
        if proxy:
            handlers.append(ur.ProxyHandler({"http": proxy, "https": proxy}))
        self.opener = ur.build_opener(*handlers)
        self.timeout = timeout

    def _req(self, method, path, params=None, body=None, ctype=None, timeout=None):
        url = f"{API}{path}"
        if params:
            url += "?" + up.urlencode({k: v for k, v in params.items() if v is not None})
        headers = {"Content-Type": ctype} if ctype else {}
        req = ur.Request(url, data=body, method=method, headers=headers)
        try:
            r = self.opener.open(req, timeout=timeout or self.timeout)
            return r.status, r.read()
        except HTTPError as e:                    # 404/409/422等も本文を読む
            return e.code, e.read()
        except URLError as e:
            return None, f"URLError: {e.reason}".encode()

    def _path(self, p): return up.quote(p.lstrip("/"), safe="/")   # 絶対パス→URL用

    @staticmethod
    def _multipart(data, filename="upload.bin", field="file"):
        # 標準ライブラリのみで multipart/form-data を組み立て（file フィールド必須）
        b = "----fugakuwebapiboundary7e3f"
        body = (
            f"--{b}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + data + f"\r\n--{b}--\r\n".encode()
        return body, f"multipart/form-data; boundary={b}"

    # --- 読み取り ---
    def status_all(self):            return self._req("GET", "/status/")
    def status(self, m=MACHINE):     return self._req("GET", f"/status/{m}")
    def queue(self, m=MACHINE, **q): return self._req("GET", f"/queue/{m}", params=q)
    def sacct(self, m=MACHINE, **q): return self._req("GET", f"/queue/{m}/sacct", params=q)
    def job_detail(self, jid, m=MACHINE): return self._req("GET", f"/queue/{m}/{jid}")
    def list_files(self, p, m=MACHINE):   # ディレクトリ一覧は末尾スラッシュ
        return self._req("GET", f"/file/{m}/{self._path(p.rstrip('/') + '/')}")
    def download(self, p, m=MACHINE):     return self._req("GET", f"/file/{m}/{self._path(p)}")
    # --- 書き込み/実行 ---
    def command(self, cmd, m=MACHINE):
        return self._req("POST", f"/command/{m}/",
                         body=json.dumps({"command": cmd}).encode(),
                         ctype="application/json")
    def upload(self, remote, data, m=MACHINE):    # 既存だと409 / file フィールド multipart
        body, ct = self._multipart(data, filename=remote.rsplit("/", 1)[-1])
        return self._req("POST", f"/file/{m}/{self._path(remote)}", body=body, ctype=ct)
    def modify(self, remote, data, m=MACHINE):    # 上書き
        body, ct = self._multipart(data, filename=remote.rsplit("/", 1)[-1])
        return self._req("PUT", f"/file/{m}/{self._path(remote)}", body=body, ctype=ct)
    def submit(self, jobfile=None, jobscript=None, qopt=None, m=MACHINE):
        d = {k: v for k, v in (("jobfile", jobfile), ("jobscript", jobscript), ("qopt", qopt)) if v}
        return self._req("POST", f"/queue/{m}/", body=json.dumps(d).encode(),
                         ctype="application/json", timeout=300)  # pjsub は時間がかかる
    def cancel(self, jid, m=MACHINE):
        return self._req("DELETE", f"/queue/{m}/{jid}")


def show(res, *codes):
    codes = codes or (200,)
    code, body = res
    flag = "OK" if code in codes else "!! FAIL"
    print(f"  -> HTTP {code} {flag}")
    try:    print("     " + json.dumps(json.loads(body), ensure_ascii=False)[:400])
    except Exception: print("     " + (body[:200].decode("utf-8", "replace") if isinstance(body, bytes) else str(body)))
    return code in codes


def jbody(res):
    try:    return json.loads(res[1])
    except Exception: return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cert", required=True, help="cert+key 結合PEM")
    ap.add_argument("--home", required=True, help="自分のHOME 例 /home/<account>")
    ap.add_argument("--max-stage", type=int, default=2)
    ap.add_argument("--proxy"); ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--qopt", default='-L "rscunit=rscunit_ft01" -L "elapse=5:00" ')
    a = ap.parse_args()

    api = FugakuAPI(a.cert, proxy=a.proxy, verify=not a.insecure)
    test_dir = f"{a.home}/webapi-test"

    print("[段1] 認証つき GET /status/ ----------------------")
    if not show(api.status_all()):
        sys.exit("status失敗。証明書/網/プロキシを確認して中断。")

    print("\n[段2] 読み取り系 ---------------------------------")
    show(api.status())
    show(api.queue(limit=5))          # No Jobs.(NG) は空=正常
    show(api.list_files(a.home))      # ファイルAPIは ~ を展開しない→絶対パス
    if a.max_stage < 3: return print("\n段2まで完了。")

    print("\n[段3] ファイル往復 -------------------------------")
    show(api.command(f"mkdir -p {test_dir}"))
    remote = f"{test_dir}/payload.txt"
    payload = b"fugaku webapi smoke test\n"
    res = api.upload(remote, payload)
    if not show(res, 200, 409): return
    if res[0] == 409: show(api.modify(remote, payload))
    rd = api.download(remote)
    print(f"  download HTTP {rd[0]} len {len(rd[1])}")
    if a.max_stage < 4: return print("\n段3まで完了。")

    print("\n[段4] コマンド実行 -------------------------------")
    for cmd in ("id", "pwd", f"ls -l {test_dir}"):
        print(" $", cmd); show(api.command(cmd))
    if a.max_stage < 5: return print("\n段4まで完了。")

    print("\n[段5] ジョブ一巡 ---------------------------------")
    js = f"{test_dir}/hello.sh"
    show(api.modify(js, b"#!/bin/bash\nhostname\ndate\nsleep 5\necho done\n"), 200, 409)
    res = api.submit(jobfile=js, qopt=a.qopt)
    if not show(res): return
    m = re.search(r"Job (\d+) submitted", jbody(res).get("output", ""))
    jid = m.group(1) if m else None
    print("  jobid =", jid)
    if jid:
        for _ in range(20):
            time.sleep(15)
            out = jbody(api.queue(jobid=jid)).get("output", [])
            st = out[0].get("status") if out else None
            print("  status:", st)
            if st in TERMINAL or st is None: break
        show(api.job_detail(jid))
        show(api.sacct(jobid=jid))
        if not a.keep:
            print("  cancel:"); show(api.cancel(jid), 200, 400)
    if not a.keep:
        print("\n[後始末]"); show(api.command(f"rm -rf {test_dir}"))
    print("\n全段完了。")


if __name__ == "__main__":
    main()
