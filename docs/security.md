日本語 | [English](security.en.md)

# 安全策ポリシー（フェーズ2）

MCPサーバの安全策は [`fugaku_policy.py`](../fugaku_policy.py) に集約し、すべて環境変数で制御する。
コード変更なしに締め付けを変えられ、全所サービス化時はユーザ別ポリシーへ拡張する想定。

## 設定（環境変数）

| 変数 | 既定 | 説明 |
|---|---|---|
| `FUGAKU_CMD_MODE` | `denylist` | `run_command` の方式: `denylist` / `allowlist` / `off` |
| `FUGAKU_ALLOW_CMDS` | 既定集合 | allowlistモードで許可する実行ファイル（カンマ/空白区切り） |
| `FUGAKU_PATH_ROOTS` | （なし） | ファイル操作を許可するパス接頭辞（`:` 区切り）。例 `/home/<account>:/vol0004/<group>/<account>` |
| `FUGAKU_MAX_NODES` | `8` | `submit_job` の最大ノード数 |
| `FUGAKU_MAX_ELAPSE_SEC` | `86400` | `submit_job` の最大経過時間（秒） |
| `FUGAKU_ALLOWED_RSCGRP` | （なし） | 許可リソースグループ（カンマ区切り） |
| `FUGAKU_MAX_BULK` | （なし） | バルクジョブのサブジョブ数の上限（`--sparam "0-9"` なら10）|
| `FUGAKU_LOCAL_ROOTS` | （なし） | `stage_in`/`stage_out` で**手元**の読み書きを許可するディレクトリ（macOS/Linux は `:`、Windows は `;` 区切り）|
| `FUGAKU_AUDIT_LOG` | （なし） | ローカル監査ログのパス。指定時、全ツール呼び出しを JSONL 追記 |
| `FUGAKU_AUDIT_REMOTE` | （なし） | 富岳上の監査集約ディレクトリ。`<dir>/<account>.jsonl` へ非同期・バッチ追記（多ユーザー履歴採取用）|

## 3つの防御層

### 1. コマンド検査（run_command）
- **denylist（既定）**: 明白に破壊的なパターンを常に拒否（`rm` の再帰＋強制削除＝`-rf`/`-Rf`/`-r -f`/`--recursive --force` 等の表記ゆれや `xargs rm -rf`/`find -exec rm -rf` も含む、フォークボム、`mkfs`/`dd`/`shred`、`shutdown` 等、`curl|sh` のネット→シェル直結）。単一ユーザの自分のアカウントで使う想定の現実的な既定。
- **allowlist（厳格）**: 既定の安全コマンド集合（読み取り・確認・ビルド系）のみ許可。コマンドチェーン（`;` `&&` `|` 等）の各セグメントを検査し、コマンド置換 `$()`/`` ` `` は一律拒否。`pjsub`/`pjdel` は意図的に非許可（`submit_job`/`cancel_job` 経由に強制し資源上限を効かせる）。サービス化・共有環境向け。
- denylistは allowlist モードでも常時併用される。

> 注意: シェルは表現力が高く、allowlistのチェーン解析は best-effort。完全な隔離にはサーバ側の制限シェルが必要で、それは今後の課題。

### 2. パス制限（stage_in / stage_out / fetch_result）
- **富岳側**: `..` を含むパスを拒否（traversal防止）、絶対パス必須。`FUGAKU_PATH_ROOTS` 設定時はその配下のみ許可。富岳は実HOME(`/vol0004/...`)と symlink(`/home/...`) があるため、両方を列挙するとよい。`fetch_result` のジョブ名も検証し（英数と `. - _ @` のみ）、ジョブ置き場の外は読ませない。
- **手元（クライアント側）**: 隠しファイル・隠しディレクトリ配下（`~/.ssh`、証明書の `~/.fugaku`、各種設定）は**設定に関わらず常に読み書きを拒否**する。富岳上の文書に仕込まれた指示でエージェントが誘導され、手元の鍵を上書き・持ち出すのを防ぐため。シンボリックリンクは解決してから判定する。`FUGAKU_LOCAL_ROOTS` 設定時はさらにその配下に限定。
- `stage_in` は `content` と `local_path` のどちらか一方の指定が必須（両方空で既存ファイルを0バイトにしてしまう事故を防ぐ）。

### 3. ジョブ資源上限（submit_job / run_job）
- ノード数・経過時間・リソースグループの上限/許可リストを強制。
- **迂回の防止**: `extra_qopt` では `-L`/`--rsc-list` の `node`・`elapse`・`rscgrp`・`rscunit`、課金グループ（`-g`/`--gname`）、ジョブ名（`-N`/`--name`）を指定できない（専用引数で指定させる）。ジョブスクリプト中の `#PJM` 指示子は、引数と**同じ値なら許可・食い違えば拒否**（コマンドラインとの優先関係に依存しないため）。`FUGAKU_MAX_BULK` 設定時はバルクジョブのサブジョブ数も制限する。

## 監査ログ
`FUGAKU_AUDIT_LOG=/path/to/audit.jsonl` を設定すると、全ツール呼び出しを1行JSONで記録:
```json
{"ts":"2026-06-28T22:10:00+0900","tool":"run_command","args":{"command":"ls -la"},"ok":true,"note":""}
```
ポリシー違反は `ok:false` と理由（`note`）付きで記録される。

## 推奨設定例
- **個人PoC（現状）**: 既定のまま（denylist）。必要なら `FUGAKU_AUDIT_LOG` を有効化。
- **共有/サービス化**: `FUGAKU_CMD_MODE=allowlist`、`FUGAKU_PATH_ROOTS` で各ユーザHOMEに限定、`FUGAKU_ALLOWED_RSCGRP`/`FUGAKU_MAX_*`（`FUGAKU_MAX_BULK` 含む）で資源制限、`FUGAKU_LOCAL_ROOTS` で手元の読み書き先を限定、`FUGAKU_AUDIT_LOG` 必須。
