"""富岳 WebAPI クライアント（X.509証明書・標準ライブラリのみ）。

cert_smoke_test.py で全エンドポイント実機検証済みの FugakuAPI を単体モジュール化したもの。
依存ゼロ（urllib + ssl）。MCPサーバ(fugaku_mcp.py)から利用する。
"""
import json, ssl
import urllib.request as ur
import urllib.parse as up
from urllib.error import HTTPError, URLError

API = "https://api.fugaku.r-ccs.riken.jp"
MACHINE = "computer"
# 完了/異常で実行キューから消えるが、明示的な終端ステータス集合（sacct側で見える）
TERMINAL = {"EXT", "CCL", "ERR", "RJT"}


class FugakuAPI:
    def __init__(self, cert, proxy=None, verify=True, timeout=60):
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(certfile=cert)          # cert+key 結合PEM
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        handlers = [ur.HTTPSHandler(context=ctx)]
        if proxy:
            handlers.append(ur.ProxyHandler({"http": proxy, "https": proxy}))
        self.opener = ur.build_opener(*handlers)
        self.timeout = timeout

    # --- 低レベル ---
    def _req(self, method, path, params=None, body=None, ctype=None, timeout=None):
        url = f"{API}{path}"
        if params:
            url += "?" + up.urlencode({k: v for k, v in params.items() if v is not None})
        headers = {"Content-Type": ctype} if ctype else {}
        req = ur.Request(url, data=body, method=method, headers=headers)
        try:
            r = self.opener.open(req, timeout=timeout or self.timeout)
            return r.status, r.read()
        except HTTPError as e:                       # 404/409/422等も本文を読む
            return e.code, e.read()
        except (URLError, TimeoutError, OSError) as e:  # 通信失敗/タイムアウト
            return None, f"{type(e).__name__}: {e}".encode()

    def _path(self, p): return up.quote(p.lstrip("/"), safe="/")

    @staticmethod
    def _multipart(data, filename="upload.bin", field="file"):
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
    def download(self, p, m=MACHINE):     return self._req("GET", f"/file/{m}/{self._path(p)}")

    # --- 書き込み/実行 ---
    def command(self, cmd, m=MACHINE, timeout=None):
        return self._req("POST", f"/command/{m}/",
                         body=json.dumps({"command": cmd}).encode(),
                         ctype="application/json", timeout=timeout)

    def upload(self, remote, data, m=MACHINE):   # 既存だと409。file フィールド multipart
        body, ct = self._multipart(data, filename=remote.rsplit("/", 1)[-1])
        return self._req("POST", f"/file/{m}/{self._path(remote)}", body=body, ctype=ct)

    def modify(self, remote, data, m=MACHINE):   # 上書き(PUT)
        body, ct = self._multipart(data, filename=remote.rsplit("/", 1)[-1])
        return self._req("PUT", f"/file/{m}/{self._path(remote)}", body=body, ctype=ct)

    def put_file(self, remote, data, m=MACHINE):  # 新規/上書きどちらでも（409なら上書き）
        res = self.upload(remote, data, m)
        if res[0] == 409:
            return self.modify(remote, data, m)
        return res

    def submit(self, jobfile=None, jobscript=None, qopt=None, m=MACHINE):
        # submitは同期・低速。JSONボディ。タイムアウト長め(300s)。
        d = {k: v for k, v in (("jobfile", jobfile), ("jobscript", jobscript), ("qopt", qopt)) if v}
        return self._req("POST", f"/queue/{m}/", body=json.dumps(d).encode(),
                         ctype="application/json", timeout=300)

    def cancel(self, jid, m=MACHINE):
        return self._req("DELETE", f"/queue/{m}/{jid}")


# --- レスポンス正規化（HTTPコードと本文statusを分離して扱う） ---
def norm(res):
    """(http_code, bytes) → 正規化dict。本文がJSONでなければ raw に格納。"""
    code, body = res
    d = {"http": code}
    try:
        j = json.loads(body)
        if isinstance(j, dict):
            d.update(j)
        else:
            d["output"] = j
    except Exception:
        d["raw"] = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    return d
