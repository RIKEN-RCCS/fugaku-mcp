#!/usr/bin/env python3
"""富岳 WebAPI MCPサーバ（スケルトン）。

検証済みの FugakuAPI を MCPツールとして公開する。Claude Code等から自然言語で
富岳のジョブ操作・ファイル転送・状態確認ができる。X.509証明書認証・依存は mcp のみ。

セットアップ:
  pip install "mcp[cli]"
  export FUGAKU_CERT=/path/to/<account>.pem      # cert+key 結合PEM（必須）
  # HOME/アカウント/グループは未指定なら起動時に証明書から自動検出される
  # 任意の上書き: FUGAKU_HOME FUGAKU_GROUP FUGAKU_ACCOUNT FUGAKU_RSCUNIT
  #               FUGAKU_PROXY FUGAKU_INSECURE(=1) FUGAKU_AUDIT_LOG FUGAKU_AUDIT_REMOTE
起動確認:  python3 fugaku_mcp.py
Claude Code登録:  .mcp.json 参照
"""
import os, re, time
from mcp.server.fastmcp import FastMCP
from fugaku_api import FugakuAPI, norm
import fugaku_policy as policy
import fugaku_update as updater

# ---- 設定（環境変数。HOME/GROUP/ACCOUNT は未指定なら証明書から自動検出） ----
CERT    = os.environ.get("FUGAKU_CERT")
RSCUNIT = os.environ.get("FUGAKU_RSCUNIT", "rscunit_ft01")
PROXY   = os.environ.get("FUGAKU_PROXY")
VERIFY  = os.environ.get("FUGAKU_INSECURE", "") != "1"
if not CERT:
    raise SystemExit("環境変数 FUGAKU_CERT（証明書PEMのパス）が未設定です。")

api = FugakuAPI(CERT, proxy=PROXY, verify=VERIFY)

# サーバ instructions（接続時にクライアント経由でエージェントへ渡る基礎ガイド）
INSTRUCTIONS = (
    "富岳をMCP経由で操作するサーバ。計算ジョブは run_job が基本（commands を渡すと"
    "投入→完了待ち→標準出力(stdout+stderr)の自動回収まで一括）。状態は cluster_status / list_jobs、"
    "自分の情報は account_info、ファイルは stage_in/stage_out（パスは絶対パス。~ はファイルAPIで展開されない）。"
    "ジョブ指定: rscgrp（例 small）, elapse=HH:MM:SS, nodes（1ノード=48コア）。"
    "submit はサーバ側で数十秒かかるのは正常。完了ジョブは実行キューから消え job_status が履歴で判定する。"
    "重い計算は必ず run_job で（run_command はログインノードの軽作業用）。"
    "使い方が不明・エラーが起きたら、まず fugaku_help ツールを呼んで対処を確認すること。"
)
mcp = FastMCP("fugaku", instructions=INSTRUCTIONS)

# ---- ユーザーコンテキスト（env優先。未指定分はAPIで自動検出しキャッシュ）----
# 多ユーザー運用では各自が自分の証明書だけ設定すればよいよう、HOME/アカウント/グループを自動取得する。
_ctx = {"account": os.environ.get("FUGAKU_ACCOUNT"),
        "home":    os.environ.get("FUGAKU_HOME"),
        "group":   os.environ.get("FUGAKU_GROUP")}


def ctx():
    """account / home / group を解決（未設定分のみ API で自動検出しキャッシュ）。"""
    if _ctx["account"] and _ctx["home"] and _ctx["group"]:
        return _ctx
    d = norm(api.command('printf "%s\\n%s\\n%s\\n" "$HOME" "$(id -un)" "$(id -gn)"'))
    lines = [l.strip() for l in str(d.get("output", "")).splitlines() if l.strip()]
    if len(lines) >= 3:
        _ctx["home"]    = _ctx["home"]    or lines[0]
        _ctx["account"] = _ctx["account"] or lines[1]
        _ctx["group"]   = _ctx["group"]   or lines[2]
        policy.set_identity(_ctx["account"])   # 監査ログにアカウントを付与
    return _ctx


def jobdir():
    return f"{ctx()['home']}/mcp-jobs"   # ジョブスクリプト/出力の置き場（ユーザーHOME配下）


# ---- リモート監査ログ（富岳上の <FUGAKU_AUDIT_REMOTE>/<account>.jsonl へ非同期・バッチ追記）----
# 各ツール呼び出しのレイテンシを増やさないよう、キュー＋バックグラウンドスレッドで送出する。
import json as _json, base64 as _b64, threading as _th, queue as _q

REMOTE_AUDIT = os.environ.get("FUGAKU_AUDIT_REMOTE")   # 例: /vol0004/<group>/<proj>/mcp-audit
_audit_q = _q.Queue()


def _audit_sink(rec):
    _audit_q.put(rec)            # 即時・非ブロッキング（送出は別スレッド）


def _audit_worker():
    while True:
        batch = [_audit_q.get()]
        try:                                    # 短時間に溜まった分はまとめて1回の追記に
            while len(batch) < 50:
                batch.append(_audit_q.get_nowait())
        except _q.Empty:
            pass
        try:
            acct = ctx().get("account") or "unknown"
            payload = "".join(_json.dumps(r, ensure_ascii=False) + "\n" for r in batch)
            b64 = _b64.b64encode(payload.encode()).decode()       # base64でシェル安全に
            d = REMOTE_AUDIT.rstrip("/")
            api.command(f"mkdir -p {d}; echo '{b64}' | base64 -d >> {d}/{acct}.jsonl")
        except Exception:
            pass                                # 失敗してもローカルログに残るので継続


if REMOTE_AUDIT:
    policy.set_remote_sink(_audit_sink)
    _th.Thread(target=_audit_worker, daemon=True).start()


# ============================ ツール ============================

@mcp.tool()
def cluster_status() -> dict:
    """富岳(computer)の稼働状態を取得する。"""
    policy.audit("cluster_status", {})
    return norm(api.status())


@mcp.tool()
def account_info() -> dict:
    """この接続で使われる富岳アカウント情報（アカウント名・HOME・グループ）を返す。
    証明書から自動検出した本人情報の確認用（多ユーザー運用での取り違え防止）。"""
    c = ctx()
    policy.audit("account_info", {})
    u = updater.cached_result()   # キャッシュのみ（低遅延）。更新情報があれば併記
    return {"account": c.get("account"), "home": c.get("home"),
            "group": c.get("group"), "rscunit": RSCUNIT, "jobdir": jobdir(),
            "version": updater.local_version(),
            "update_available": u.get("update_available"), "latest_version": u.get("latest")}


@mcp.tool()
def fugaku_help(topic: str = "", lang: str = "") -> dict:
    """富岳の使い方・よくあるエラーの対処を返す。ジョブの投げ方が不明なとき、
    エラー（却下/タイムアウト/権限/却下コマンド等）が起きたときに最初に参照する。
    topic を指定すると、その語を含む見出しのセクションのみ返す（例: "エラー", "run_job", "MPI"）。
    lang="en" で英語ガイドを返す（既定は日本語）。"""
    policy.audit("fugaku_help", {"topic": topic, "lang": lang})
    docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    fname = "agent-guide.en.md" if str(lang).lower().startswith("en") else "agent-guide.md"
    path = os.path.join(docs, fname)
    if not os.path.isfile(path):                       # 英語版が無ければ日本語版にフォールバック
        path = os.path.join(docs, "agent-guide.md")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return {"error": "ガイドが見つかりません", "hint": "run_job で計算、stage_in/out でファイル、エラー時はrscgrp/elapse/nodesと権限を確認"}
    if topic:
        sections = ["## " + s for s in text.split("\n## ")[1:]]   # 各 "## " セクション
        hit = [s for s in sections if topic.lower() in s.lower()]
        if hit:
            return {"topic": topic, "content": "\n\n".join(hit)}
    return {"content": text}


@mcp.tool()
def search_manual(query: str, lang: str = "ja", top: int = 3) -> dict:
    """公式富岳マニュアルを検索し、該当箇所の抜粋とURLを返す。
    fugaku_help で見つからない・より詳しい情報が要るときに範囲を広げて探す用（オンデマンド取得）。
    query: 探したい語（日本語/英語）。 lang: "ja"（既定）/"en"。 top: 取得ページ数。"""
    import urllib.request as _ur, html as _html
    policy.audit("search_manual", {"query": query, "lang": lang})
    lang = "en" if str(lang).lower().startswith("en") else "ja"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "manual-pages.json")
    try:
        with open(path, encoding="utf-8") as f:
            idx = _json.load(f)
    except Exception:
        return {"error": "manual-pages.json が見つかりません",
                "manual_index": "https://www.r-ccs.riken.jp/fugaku/user-manuals/"}
    q = query.strip()
    toks = [t for t in re.split(r"\s+", q) if t] or [q]

    def score(pg):
        hay = ((pg.get("title_" + lang) or "") + " " + pg.get("kw", "")).lower()
        return sum(hay.count(t.lower()) for t in toks) + (2 if q.lower() in hay else 0)

    hits = []
    for pg in sorted(idx["pages"], key=score, reverse=True):
        if score(pg) <= 0:
            continue
        url = idx["guides"][pg["guide"]][lang] + pg["rel"]
        try:
            raw = _ur.urlopen(_ur.Request(url, headers={"User-Agent": "fugaku-mcp"}),
                              timeout=15).read().decode("utf-8", "replace")
        except Exception:
            continue
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)      # HTML→段落テキスト
        raw = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|section)>", "\n\n", raw)
        raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
        text = _html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
        paras = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
        paras = [p for p in paras if p]
        # 一致段落の位置から、直後の本文も含めた窓を抜粋（見出しだけにならないように）
        idxs = [i for i, p in enumerate(paras) if len(p) > 8
                and any(t.lower() in p.lower() for t in toks + [q])]
        if idxs:
            windows = []
            last = -10
            for i in idxs[:3]:
                if i - last < 6:      # 近接する一致はまとめる
                    continue
                windows.append("\n".join(paras[i:i + 7]))
                last = i
            excerpt = ("\n…\n".join(windows))[:1800]
        else:
            excerpt = ""
        hits.append({"title": pg.get("title_" + lang), "url": url,
                     "excerpt": excerpt or "(一致段落なし。URLを参照)"})
        if len(hits) >= max(1, top):
            break
    return {"query": q, "lang": lang, "results": hits,
            "manual_index": idx["guides"]["use"][lang] + "index.html",
            "note": "該当が薄い場合は manual_index か https://www.r-ccs.riken.jp/fugaku/user-manuals/ を参照。"}


@mcp.tool()
def check_update() -> dict:
    """fugaku-mcp の更新があるか確認する（公開リポの最新バージョンと比較）。
    update_available が true なら、リポジトリで ./update.sh を実行して更新（更新後はクライアント再起動）。"""
    policy.audit("check_update", {})
    return updater.check(force=True)


@mcp.tool()
def list_jobs(completed: bool = False, limit: int = 20) -> dict:
    """自分のジョブ一覧を取得する。completed=False で実行中、True で完了済み(直近24h)。"""
    policy.audit("list_jobs", {"completed": completed, "limit": limit})
    res = api.sacct(limit=limit) if completed else api.queue(limit=limit)
    d = norm(res)
    # 空キューは status:"NG"/"No Jobs." で返る → 正常な空として整える
    if d.get("status") == "NG" and "No Jobs" in str(d.get("error", "")):
        return {"http": d["http"], "jobs": []}
    return {"http": d["http"], "jobs": d.get("output") or []}


@mcp.tool()
def run_command(command: str) -> dict:
    """ログインノードで任意コマンドを実行し stdout/stderr を返す。
    注意: 計算ノードではなくログインノード上での軽量コマンド用（ビルド/ls/確認等）。
    安全策: FUGAKU_CMD_MODE（denylist/allowlist/off）で許可範囲を制御する。"""
    try:
        policy.check_command(command)
    except policy.PolicyError as e:
        policy.audit("run_command", {"command": command}, ok=False, note=str(e))
        raise
    policy.audit("run_command", {"command": command})
    return norm(api.command(command))


@mcp.tool()
def stage_in(remote_path: str, content: str = "", local_path: str = "") -> dict:
    """ファイルを富岳へ転送する。content（文字列）か local_path（手元ファイル）のどちらかを指定。
    既存ファイルは自動で上書きする。"""
    policy.check_path(remote_path)
    if local_path:
        with open(local_path, "rb") as f:
            data = f.read()
    else:
        data = content.encode()
    policy.audit("stage_in", {"remote_path": remote_path, "bytes": len(data)})
    return norm(api.put_file(remote_path, data))


@mcp.tool()
def stage_out(remote_path: str, local_path: str = "") -> dict:
    """富岳からファイルを取得する。local_path 指定時はそこへ保存、未指定なら本文を返す（テキスト想定）。"""
    policy.check_path(remote_path)
    policy.audit("stage_out", {"remote_path": remote_path, "local_path": local_path})
    code, body = api.download(remote_path)
    if code != 200:
        return {"http": code, "error": body.decode("utf-8", "replace")}
    if local_path:
        with open(local_path, "wb") as f:
            f.write(body)
        return {"http": code, "saved": local_path, "bytes": len(body)}
    return {"http": code, "bytes": len(body), "content": body.decode("utf-8", "replace")}


def _result_path(name: str) -> str:
    return f"{jobdir()}/{name}.result"


def _submit_core(script, name, nodes, elapse, rscgrp, extra_qopt):
    """ジョブ投入の共通処理（投入→jobid抽出→タイムアウト時はキュー照合で復旧）。"""
    if not re.match(r"^[A-Za-z][A-Za-z0-9._@-]{0,62}$", name):
        raise ValueError("ジョブ名は英字始まり・英数と . - _ @ のみ・63文字以内")
    policy.check_job(nodes, elapse, rscgrp)
    jd = jobdir()
    api.command(f"mkdir -p {jd}")
    remote = f"{jd}/{name}.sh"
    up_res = api.put_file(remote, script.encode())
    if norm(up_res).get("http") != 200:
        return {"step": "upload", **norm(up_res)}

    group = ctx().get("group")
    qopt = (f'-L "rscunit={RSCUNIT}" -L "rscgrp={rscgrp}" -L "node={nodes}" '
            f'-L "elapse={elapse}" -N {name} ')
    if group:      qopt += f"-g {group} "
    if extra_qopt: qopt += extra_qopt

    res = api.submit(jobfile=remote, qopt=qopt)
    d = norm(res)
    m = re.search(r"Job (\d+) submitted", str(d.get("output", "")))
    if m:
        return {"http": d["http"], "jobid": m.group(1), "output": d.get("output")}
    # タイムアウト等でjobid不明 → 投入は成功している可能性。名前で実行キューを照合して復旧。
    if d.get("http") is None:
        time.sleep(5)
        for j in (norm(api.queue(limit=50)).get("output") or []):
            if str(j.get("name", "")).startswith(name):
                return {"http": None, "jobid": str(j.get("jobid")),
                        "note": "submitはタイムアウトしたがキューに発見（投入成功）", "job": j}
    return {"step": "submit", **d}


def _status_core(jobid):
    """状態判定の共通処理（実行中→active / 消失→sacct照合でcompleted）。"""
    out = norm(api.queue(jobid=jobid)).get("output")
    if out:
        return {"phase": "active", "status": out[0].get("status"), "job": out[0]}
    for j in (norm(api.sacct(limit=100)).get("output") or []):  # sacctはjobid絞り不可な場合があるため照合
        if str(j.get("jobid")) == str(jobid):
            return {"phase": "completed", "status": j.get("status"), "job": j}
    return {"phase": "unknown",
            "note": "実行キューにもsacct(直近24h)にも無し。完了から時間が経過した可能性。"}


@mcp.tool()
def submit_job(script: str, name: str = "job", nodes: int = 1,
               elapse: str = "00:10:00", rscgrp: str = "small",
               extra_qopt: str = "") -> dict:
    """バッチジョブを富岳に投入する（低レベル）。完了待ち・結果回収まで一括なら run_job を使う。

    script: ジョブスクリプト本文（#!/bin/bash で始まるシェル）。
    name: ジョブ名（英字始まり・英数と . - _ @ のみ・63文字以内）。
    nodes: ノード数（上限 FUGAKU_MAX_NODES）。 elapse: 経過時間制限 HH:MM:SS。
    rscgrp: リソースグループ（例 small）。 extra_qopt: 追加の pjsub オプション。
    戻り値に jobid を含む。状態は job_status で別途ポーリングすること（submitは同期・低速）。
    """
    policy.audit("submit_job", {"name": name, "nodes": nodes, "elapse": elapse, "rscgrp": rscgrp})
    return _submit_core(script, name, nodes, elapse, rscgrp, extra_qopt)


@mcp.tool()
def run_job(commands: str, name: str = "job", nodes: int = 1, elapse: str = "00:10:00",
            rscgrp: str = "small", wait_sec: int = 300, extra_qopt: str = "") -> dict:
    """コマンド群を富岳でバッチ実行し、完了まで待って標準出力を自動回収する一括ツール。

    commands: 実行したいシェルコマンド（複数行可・シェバン不要）。stdout/stderr は
              {JOBDIR}/<name>.result に集約され、完了時に result として返る。
    wait_sec: 完了待ちの最大秒数。超過時は jobid を返すので後で fetch_result/job_status で確認。
    MPIジョブ: Fujitsu MPI(PLE)は各ランクの標準出力を $HOME/output.<jobid>/ に書き出す（-std/-of は無視）。
              run_job はこれを完了後に自動回収して mpi_output に入れる（回収後は削除）。
    その他の引数は submit_job と同じ（資源上限ポリシーが適用される）。
    """
    body = commands.split("\n", 1)[1] if commands.startswith("#!") and "\n" in commands else commands
    result = _result_path(name)
    # cwd を $HOME に固定 → MPIランク出力 $HOME/output.<jobid>/ の場所を決定的にする
    script = f'#!/bin/bash\ncd "$HOME"\n{{\n{body}\n}} > {result} 2>&1\n'
    policy.audit("run_job", {"name": name, "nodes": nodes, "elapse": elapse, "rscgrp": rscgrp})

    sub = _submit_core(script, name, nodes, elapse, rscgrp, extra_qopt)
    jid = sub.get("jobid")
    if not jid:
        return {"phase": "submit_failed", **sub}

    waited, interval = 0, 10
    st = _status_core(jid)
    while st.get("phase") == "active" and waited < wait_sec:
        time.sleep(interval); waited += interval
        st = _status_core(jid)
    if st.get("phase") == "active":
        return {"jobid": jid, "phase": "active", "status": st.get("status"), "result_path": result,
                "note": f"{wait_sec}秒以内に未完了。job_status('{jid}') か fetch_result('{name}') で後から確認を。"}

    code, data = api.download(result)
    ret = {"jobid": jid, "phase": st.get("phase"), "status": st.get("status"), "result_path": result,
           "result": data.decode("utf-8", "replace") if code == 200 else f"(結果取得失敗 http={code})"}
    # MPIランク出力（$HOME/output.<jid>）があれば回収して片付ける
    mpi = norm(api.command(
        f'd="$HOME/output.{jid}"; if [ -d "$d" ]; then '
        f'cat "$d"/*/*/stdout.* 2>/dev/null; rm -rf "$d"; fi')).get("output", "")
    if str(mpi).strip():
        ret["mpi_output"] = mpi
    return ret


@mcp.tool()
def fetch_result(name: str) -> dict:
    """run_job で実行したジョブの結果ファイル({JOBDIR}/<name>.result)を取得する。"""
    result = _result_path(name)
    policy.audit("fetch_result", {"name": name, "result_path": result})
    code, data = api.download(result)
    if code != 200:
        return {"http": code, "error": data.decode("utf-8", "replace"), "result_path": result}
    return {"http": code, "result_path": result, "bytes": len(data),
            "content": data.decode("utf-8", "replace")}


@mcp.tool()
def job_status(jobid: str) -> dict:
    """ジョブの状態を返す。実行中なら active、消えていれば完了済みとして sacct を照合。

    富岳では完了ジョブは実行キューから消え、最終状態(EXT等)は sacct(直近24h)に出る。
    """
    policy.audit("job_status", {"jobid": jobid})
    return _status_core(jobid)


@mcp.tool()
def cancel_job(jobid: str) -> dict:
    """実行中/待機中のジョブを取消する(pjdel)。完了済みなら does not exist が返る(無害)。"""
    policy.audit("cancel_job", {"jobid": jobid})
    return norm(api.cancel(jobid))


if __name__ == "__main__":
    import sys
    # 起動時に「本人情報＋ポリシー」をstderrへ（stdoutはMCPプロトコル専用なので使わない）
    try:
        c = ctx()   # 証明書から本人情報を自動検出して表示（多ユーザー運用での確認用）
        print(f"[fugaku-mcp] identity: account={c.get('account')} home={c.get('home')} "
              f"group={c.get('group')}", file=sys.stderr)
    except Exception as e:
        print(f"[fugaku-mcp] 本人情報の自動検出に失敗（証明書/疎通を確認）: {e}", file=sys.stderr)
    print(f"[fugaku-mcp] policy: {policy.summary()}", file=sys.stderr)
    print(f"[fugaku-mcp] version: {updater.local_version()}", file=sys.stderr)

    # オプトインの自動更新（既定OFF）。自分の富岳権限で動くコードを自動取得・実行するため要注意。
    if os.environ.get("FUGAKU_AUTO_UPDATE") == "1":
        try:
            import subprocess
            r = subprocess.run(["bash", os.path.join(os.path.dirname(os.path.abspath(__file__)), "update.sh")],
                               capture_output=True, text=True, timeout=120)
            print("[fugaku-mcp] auto-update:\n" + (r.stdout or "") + (r.stderr or ""), file=sys.stderr)
            print("[fugaku-mcp] 自動更新を実行。新コードの反映には再起動が必要です。", file=sys.stderr)
        except Exception as e:
            print(f"[fugaku-mcp] 自動更新に失敗: {e}", file=sys.stderr)

    # 更新チェック（既定: 通知のみ・非ブロッキング・best-effort）
    def _notify_update():
        u = updater.check()
        if u.get("update_available"):
            print(f"[fugaku-mcp] 🔔 新しいバージョン {u.get('latest')} があります"
                  f"（現在 {u.get('current')}）。{u.get('how_to_update')}", file=sys.stderr)
    import threading as _t2
    _t2.Thread(target=_notify_update, daemon=True).start()

    mcp.run()
