"""富岳MCPサーバの安全策ポリシー（フェーズ2）。

run_command の許可/拒否・ファイルパス制限・ジョブ資源上限・監査ログを一元管理する。
すべて環境変数で設定でき、コード変更なしに締め付けを変えられる。全所サービス化時は
ここをポリシーファイル/ユーザ別設定へ拡張する想定。

環境変数:
  FUGAKU_CMD_MODE     run_command の方式: denylist(既定) | allowlist | off
  FUGAKU_ALLOW_CMDS   allowlistモードで許可する実行ファイル（カンマ区切り。未指定で既定集合）
  FUGAKU_PATH_ROOTS   ファイル操作を許可するパス接頭辞（コロン区切り。未指定なら接頭辞制限なし）
  FUGAKU_MAX_NODES        submit_job の最大ノード数（既定 8）
  FUGAKU_MAX_ELAPSE_SEC   submit_job の最大経過時間秒（既定 86400）
  FUGAKU_ALLOWED_RSCGRP   許可リソースグループ（カンマ区切り。未指定で制限なし）
  FUGAKU_MAX_BULK         バルクジョブのサブジョブ数上限（未指定・0 で制限なし）
  FUGAKU_LOCAL_ROOTS      stage_in/stage_out で手元の読み書きを許可するディレクトリ
                          （macOS/Linux はコロン、Windows はセミコロン区切り。未指定なら制限なし。
                           隠しファイル・隠しディレクトリ配下は設定に関わらず常に拒否）
  FUGAKU_AUDIT_LOG        監査ログのパス（指定時、全ツール呼び出しをJSONL追記）
"""
import os, re, json, time, shlex


class PolicyError(ValueError):
    """ポリシー違反。MCPツールはこれを呼び出し元へエラーとして返す。"""


# ---- コマンド方針 ----
CMD_MODE = os.environ.get("FUGAKU_CMD_MODE", "denylist").lower()

# 明白に破壊的なパターン（denylist/allowlist両方で常に拒否）
# ※ rm の再帰＋強制削除（-rf / -Rf / -r -f / --recursive --force 等）は _rm_recursive_force で判定する
_DENY_PATTERNS = [
    r"\brm\b[^;&|\n]*\s(/|~|\$HOME|/home|/vol)(\s|/|\*|$)",         # rm 対象がHOME/ルート系(同一コマンド内に限定)
    r":\s*\(\s*\)\s*\{",            # フォークボム
    r"\bmkfs\b", r"\bdd\s+if=", r"\bshred\b",
    r">\s*/dev/sd", r"\bchmod\s+-R\s+0",
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\bcurl\b[^|]*\|\s*(ba)?sh", r"\bwget\b[^|]*\|\s*(ba)?sh",      # ネット→シェル直結
]
_DENY = [re.compile(p) for p in _DENY_PATTERNS]

# allowlistモードの既定許可コマンド（読み取り/確認/ビルド系。破壊系・ジョブ系は除外）
# ※ pjsub/pjdel は submit_job/cancel_job 経由に強制するため意図的に含めない
_DEFAULT_ALLOW = (
    "ls cat head tail wc grep egrep fgrep find file stat pwd id whoami hostname "
    "date echo printf df du quota env which type uname sort uniq cut awk sed tr "
    "diff tar gzip gunzip zip unzip mkdir cp mv touch ln "
    "module spack make cmake gcc g++ gfortran mpicc mpifort mpiFCC fcc FCC frt "
    "python python3 pip pip3 conda git pjstat pjacl pjshowrsc"
).split()
ALLOW_CMDS = set((os.environ.get("FUGAKU_ALLOW_CMDS") or " ".join(_DEFAULT_ALLOW)).replace(",", " ").split())

_SEG_SEP = re.compile(r"[;&|\n]+")          # コマンド連結の分割
_ENV_ASSIGN = re.compile(r"^\w+=")


def _segments(cmd):
    return [s.strip() for s in _SEG_SEP.split(cmd) if s.strip()]


def _first_exec(seg):
    try:
        toks = shlex.split(seg)
    except ValueError:
        toks = seg.split()
    i = 0
    while i < len(toks) and _ENV_ASSIGN.match(toks[i]):  # VAR=val を読み飛ばす
        i += 1
    if i < len(toks) and toks[i] in ("sudo", "env", "nohup", "time"):
        i += 1
    return toks[i] if i < len(toks) else ""


def _rm_recursive_force(cmd):
    """rm に再帰(-r/-R/--recursive)と強制(-f/--force)が両方付いているか。
    フラグの大文字・分割・順序（-Rf, -r -f, -fR, --recursive --force）や xargs rm / find -exec rm も拾う。"""
    for seg in _segments(cmd):
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        for i, t in enumerate(toks):
            if t != "rm" and not t.endswith("/rm"):
                continue
            recursive = force = False
            for a in toks[i + 1:]:
                if a == "--":
                    break
                if a in ("--recursive",):
                    recursive = True
                elif a in ("--force",):
                    force = True
                elif a.startswith("-") and not a.startswith("--"):
                    recursive |= ("r" in a or "R" in a)
                    force |= "f" in a
            if recursive and force:
                return True
    return False


def check_command(cmd: str):
    """run_command のコマンドを検査。違反時 PolicyError。"""
    if _rm_recursive_force(cmd):           # denylistは常に適用
        raise PolicyError("危険なコマンドとして拒否: rm の再帰＋強制削除（-rf 等）")
    for rx in _DENY:
        if rx.search(cmd):
            raise PolicyError(f"危険なコマンドとして拒否: /{rx.pattern}/ に一致")
    if CMD_MODE == "allowlist":
        if re.search(r"\$\(|`", cmd):      # コマンド置換は安全に解析できないため拒否
            raise PolicyError("allowlistモードではコマンド置換 $()/`` は不可")
        for seg in _segments(cmd):
            exe = _first_exec(seg)
            if exe and exe not in ALLOW_CMDS:
                raise PolicyError(f"allowlist非許可コマンド: {exe!r}（許可は FUGAKU_ALLOW_CMDS で調整）")


# ---- パス制限 ----
PATH_ROOTS = [p for p in os.environ.get("FUGAKU_PATH_ROOTS", "").split(":") if p]


def check_path(path: str):
    """ファイル操作対象パスを検査。絶対パス必須・traversal禁止・（設定時）許可root配下のみ。"""
    if ".." in path.split("/"):
        raise PolicyError("パスに '..' を含められません（traversal防止）")
    if not path.startswith(("/", "~")):
        raise PolicyError("絶対パス（または ~ 始まり）を指定してください")
    if PATH_ROOTS and not any(path.startswith(r) for r in PATH_ROOTS):
        raise PolicyError(f"許可パス {PATH_ROOTS} の配下のみ操作できます: {path}")


# ---- 手元（クライアント側）パス制限 ----
LOCAL_ROOTS = [os.path.realpath(os.path.expanduser(p))
               for p in os.environ.get("FUGAKU_LOCAL_ROOTS", "").split(os.pathsep) if p]


def check_local_path(path: str) -> str:
    """stage_in/stage_out が手元で読み書きするパスを検査し、解決済みの絶対パスを返す。

    隠しファイル・隠しディレクトリ（~/.ssh、~/.fugaku の証明書、各種設定）は常に拒否する。
    富岳側の文書に仕込まれた指示でエージェントが誘導され、手元の鍵や設定を上書き・持ち出すのを防ぐため。
    シンボリックリンクは解決してから判定する（リンク経由の回り込み防止）。"""
    rp = os.path.realpath(os.path.expanduser(path))
    if any(part.startswith(".") for part in rp.split(os.sep) if part):
        raise PolicyError(f"隠しファイル・隠しディレクトリ配下は読み書きできません（鍵・設定の保護）: {rp}")
    if LOCAL_ROOTS and not any(rp == r or rp.startswith(r.rstrip(os.sep) + os.sep) for r in LOCAL_ROOTS):
        raise PolicyError(f"手元の許可ディレクトリ {LOCAL_ROOTS} の配下のみ読み書きできます: {rp}")
    return rp


# ---- ジョブ資源上限 ----
MAX_NODES = int(os.environ.get("FUGAKU_MAX_NODES", "8"))
MAX_ELAPSE_SEC = int(os.environ.get("FUGAKU_MAX_ELAPSE_SEC", "86400"))
ALLOWED_RSCGRP = [g for g in os.environ.get("FUGAKU_ALLOWED_RSCGRP", "").replace(",", " ").split() if g]


def _elapse_sec(s):
    try:
        parts = [int(x) for x in str(s).split(":")]
    except ValueError:
        raise PolicyError(f"elapse の形式が不正: {s!r}（HH:MM:SS）")
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, sec = parts[-3:]
    return h * 3600 + m * 60 + sec


def check_job(nodes: int, elapse: str, rscgrp: str):
    if nodes > MAX_NODES:
        raise PolicyError(f"nodes={nodes} は上限 {MAX_NODES} を超過")
    if _elapse_sec(elapse) > MAX_ELAPSE_SEC:
        raise PolicyError(f"elapse={elapse} は上限 {MAX_ELAPSE_SEC}秒 を超過")
    if ALLOWED_RSCGRP and rscgrp not in ALLOWED_RSCGRP:
        raise PolicyError(f"rscgrp={rscgrp!r} は許可外（許可: {ALLOWED_RSCGRP}）")


# ---- pjsub オプション（extra_qopt と #PJM 指示子）の検査 ----
# nodes/elapse/rscgrp と課金グループは専用引数でのみ指定させる。extra_qopt や #PJM で上書きできると
# check_job の上限（FUGAKU_MAX_NODES 等）が意味を失うため、投入される全オプションを検査する。
MAX_BULK = int(os.environ.get("FUGAKU_MAX_BULK", "0") or 0)
_RESERVED_RSC = ("node", "elapse", "rscgrp", "rscunit")
_PJSUB_OPTS = {"-L": "rsc", "--rsc-list": "rsc", "-g": "group", "--gname": "group",
               "-N": "name", "--name": "name", "--sparam": "sparam"}


def _parse_pjsub_opts(opts, where):
    """pjsub オプション文字列を [(種別, 値)] に分解する（検査用）。-Lx / --rsc-list=x の連結形も扱う。"""
    try:
        toks = shlex.split(opts or "")
    except ValueError as e:
        raise PolicyError(f"{where} を解釈できません: {e}")
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        i += 1
        if t == "--bulk":
            out.append(("bulk", None))
            continue
        for flag, kind in _PJSUB_OPTS.items():
            joined = flag + ("=" if flag.startswith("--") else "")
            if t == flag:
                out.append((kind, toks[i] if i < len(toks) else ""))
                i += 1
                break
            if t.startswith(joined) and len(t) > len(joined):
                out.append((kind, t[len(joined):]))
                break
    return out


def check_submit(nodes, elapse, rscgrp, *, rscunit, group, extra_qopt="", script=""):
    """投入前の総合検査: 資源上限（check_job）に加え、extra_qopt と #PJM 指示子による上書きを拒否する。

    extra_qopt: node/elapse/rscgrp/rscunit・課金グループ・ジョブ名の指定を一律拒否（専用引数で指定させる）。
    #PJM 指示子: 引数と同じ値なら許可、食い違えば拒否（コマンドラインとの優先関係に依存しないように）。"""
    check_job(nodes, elapse, rscgrp)
    expected = {"node": str(nodes), "elapse": _elapse_sec(elapse), "rscgrp": rscgrp, "rscunit": rscunit}
    opts = []
    for line in (script or "").splitlines():
        s = line.strip()
        if s.startswith("#PJM"):
            opts += [(k, v, "#PJM 指示子") for k, v in _parse_pjsub_opts(s[4:], "#PJM 指示子")]
    opts += [(k, v, "extra_qopt") for k, v in _parse_pjsub_opts(extra_qopt, "extra_qopt")]

    bulk, sparam = False, None
    for kind, val, where in opts:
        if kind == "rsc":
            for item in (val or "").split(","):
                key, _, v = item.strip().partition("=")
                key = key.strip()
                if key not in _RESERVED_RSC:
                    continue
                if where == "extra_qopt":
                    raise PolicyError(f"extra_qopt で {key} は指定できません（nodes / elapse / rscgrp 引数で指定してください）")
                same = _elapse_sec(v.strip()) == expected[key] if key == "elapse" else v.strip() == expected[key]
                if not same:
                    raise PolicyError(f"#PJM 指示子の {key}={v.strip()} が引数と食い違います（引数側: {expected[key]}）")
        elif kind == "group":
            if where == "extra_qopt":
                raise PolicyError("extra_qopt で課金グループ（-g/--gname）は指定できません（自分のグループが自動で付与されます）")
            if not group or val != group:
                raise PolicyError(f"#PJM 指示子の課金グループ {val!r} が自分のグループ {group!r} と食い違います")
        elif kind == "name" and where == "extra_qopt":
            raise PolicyError("extra_qopt でジョブ名（-N/--name）は指定できません（name 引数で指定してください）")
        elif kind == "bulk":
            bulk = True
        elif kind == "sparam":
            sparam = val
    if bulk and MAX_BULK:
        m = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", sparam or "")
        if not m:
            raise PolicyError(f"バルクジョブの --sparam を解釈できません（例 \"0-9\"）: {sparam!r}")
        n = int(m.group(2)) - int(m.group(1)) + 1
        if n > MAX_BULK:
            raise PolicyError(f"バルクジョブのサブジョブ数 {n} は上限 {MAX_BULK} を超過")


# ---- 監査ログ ----
AUDIT_LOG = os.environ.get("FUGAKU_AUDIT_LOG")
IDENTITY = os.environ.get("FUGAKU_ACCOUNT")   # 監査ログに付与するアカウント（自動検出時に set_identity で更新）


def set_identity(account):
    """監査ログに付与するアカウント名を設定（起動時の自動検出後に呼ばれる）。"""
    global IDENTITY
    IDENTITY = account


_remote_sink = None   # 富岳側へ監査レコードを送るコールバック（fugaku_mcp が登録）


def set_remote_sink(fn):
    """監査レコードのリモート送出シンクを登録（fugaku_mcp が富岳上ファイルへ追記する用）。"""
    global _remote_sink
    _remote_sink = fn


def audit(tool: str, args: dict, ok: bool = True, note: str = ""):
    """全ツール呼び出しを記録（ローカルJSONL: FUGAKU_AUDIT_LOG / リモート: 登録シンク）。"""
    if not AUDIT_LOG and _remote_sink is None:
        return
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "account": IDENTITY,
        "tool": tool, "args": args, "ok": ok, "note": note,
    }
    if AUDIT_LOG:
        try:
            # encoding必須: 未指定だとロケール依存になり、日本語Windows(cp932)で
            # ensure_ascii=False の日本語を書けず UnicodeEncodeError になる。
            with open(AUDIT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass  # ログ失敗で本処理は止めない
    if _remote_sink:
        try:
            _remote_sink(rec)
        except Exception:
            pass  # リモート送出失敗で本処理は止めない（ローカルログに残る）


def summary() -> dict:
    """現在のポリシー設定（起動時の確認用）。"""
    return {
        "cmd_mode": CMD_MODE,
        "allow_cmds": sorted(ALLOW_CMDS) if CMD_MODE == "allowlist" else "(denylistのみ)",
        "path_roots": PATH_ROOTS or "(接頭辞制限なし)",
        "max_nodes": MAX_NODES, "max_elapse_sec": MAX_ELAPSE_SEC,
        "allowed_rscgrp": ALLOWED_RSCGRP or "(制限なし)",
        "max_bulk": MAX_BULK or "(制限なし)",
        "local_roots": LOCAL_ROOTS or "(制限なし・隠しファイルは常に拒否)",
        "audit_log": AUDIT_LOG or "(無効)",
    }
