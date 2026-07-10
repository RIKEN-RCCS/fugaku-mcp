"""更新チェック（best-effort・標準ライブラリのみ）。

公開リポの VERSION（main ブランチ）と手元の VERSION を比較し、新しい版があるか判定する。
ネットワーク失敗時は静かに諦める（本処理は止めない）。結果は24時間キャッシュ。

環境変数:
  FUGAKU_NO_UPDATE_CHECK=1   更新チェックを無効化
  FUGAKU_UPDATE_URL          比較に使う VERSION の raw URL（既定は公開リポ main）
"""
import os, json, time, ssl
import urllib.request as ur

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(HERE, "VERSION")
CACHE_FILE = os.path.join(HERE, ".update-cache.json")
REPO_URL = "https://github.com/RIKEN-RCCS/fugaku-mcp"
REMOTE_VERSION_URL = os.environ.get(
    "FUGAKU_UPDATE_URL",
    "https://raw.githubusercontent.com/RIKEN-RCCS/fugaku-mcp/main/VERSION")
TTL = 86400  # 24h


def local_version():
    try:
        with open(VERSION_FILE) as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def _vtuple(s):
    out = []
    for p in str(s).split("."):
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return tuple(out)


def _fetch_remote(timeout):
    req = ur.Request(REMOTE_VERSION_URL, headers={"User-Agent": "fugaku-mcp-update"})
    with ur.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return r.read().decode("utf-8", "replace").strip()


def _result(cur, latest, cached=False):
    avail = bool(latest) and _vtuple(latest) > _vtuple(cur)
    return {
        "checked": True, "cached": cached, "current": cur, "latest": latest,
        "update_available": avail,
        "how_to_update": ("リポジトリで ./update.sh を実行（または git pull）。更新後はMCPクライアントを再起動。"
                          if avail else None),
        "repo": REPO_URL,
    }


def cached_result():
    """ネットワークを使わず、キャッシュがあればそれで判定（account_info 等の低遅延用）。"""
    cur = local_version()
    try:
        with open(CACHE_FILE) as f:
            c = json.load(f)
        return _result(cur, c.get("latest"), cached=True)
    except Exception:
        return {"checked": False, "current": cur}


def check(force=False, timeout=5):
    """更新チェック本体。force=True で必ずネットワーク参照、それ以外は24hキャッシュ。"""
    if os.environ.get("FUGAKU_NO_UPDATE_CHECK") == "1":
        return {"checked": False, "reason": "disabled", "current": local_version()}
    cur = local_version()
    if not force:
        try:
            with open(CACHE_FILE) as f:
                c = json.load(f)
            if time.time() - c.get("ts", 0) < TTL:
                return _result(cur, c.get("latest"), cached=True)
        except Exception:
            pass
    try:
        latest = _fetch_remote(timeout)
    except Exception as e:
        return {"checked": False, "reason": type(e).__name__, "current": cur}
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"ts": time.time(), "latest": latest}, f)
    except OSError:
        pass
    return _result(cur, latest)
