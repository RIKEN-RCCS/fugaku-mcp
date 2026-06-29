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
  FUGAKU_AUDIT_LOG        監査ログのパス（指定時、全ツール呼び出しをJSONL追記）
"""
import os, re, json, time, shlex


class PolicyError(ValueError):
    """ポリシー違反。MCPツールはこれを呼び出し元へエラーとして返す。"""


# ---- コマンド方針 ----
CMD_MODE = os.environ.get("FUGAKU_CMD_MODE", "denylist").lower()

# 明白に破壊的なパターン（denylist/allowlist両方で常に拒否）
_DENY_PATTERNS = [
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r",  # rm -rf / -fr
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


def check_command(cmd: str):
    """run_command のコマンドを検査。違反時 PolicyError。"""
    for rx in _DENY:                       # denylistは常に適用
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
            with open(AUDIT_LOG, "a") as f:
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
        "audit_log": AUDIT_LOG or "(無効)",
    }
