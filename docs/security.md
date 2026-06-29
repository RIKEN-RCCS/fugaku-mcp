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
| `FUGAKU_AUDIT_LOG` | （なし） | ローカル監査ログのパス。指定時、全ツール呼び出しを JSONL 追記 |
| `FUGAKU_AUDIT_REMOTE` | （なし） | 富岳上の監査集約ディレクトリ。`<dir>/<account>.jsonl` へ非同期・バッチ追記（多ユーザー履歴採取用）|

## 3つの防御層

### 1. コマンド検査（run_command）
- **denylist（既定）**: 明白に破壊的なパターンを常に拒否（`rm -rf` 系、フォークボム、`mkfs`/`dd`/`shred`、`shutdown` 等、`curl|sh` のネット→シェル直結）。単一ユーザの自分のアカウントで使う想定の現実的な既定。
- **allowlist（厳格）**: 既定の安全コマンド集合（読み取り・確認・ビルド系）のみ許可。コマンドチェーン（`;` `&&` `|` 等）の各セグメントを検査し、コマンド置換 `$()`/`` ` `` は一律拒否。`pjsub`/`pjdel` は意図的に非許可（`submit_job`/`cancel_job` 経由に強制し資源上限を効かせる）。サービス化・共有環境向け。
- denylistは allowlist モードでも常時併用される。

> 注意: シェルは表現力が高く、allowlistのチェーン解析は best-effort。完全な隔離にはサーバ側の制限シェルが必要で、それは今後の課題。

### 2. パス制限（stage_in / stage_out）
- `..` を含むパスを拒否（traversal防止）、絶対パス必須。
- `FUGAKU_PATH_ROOTS` 設定時はその配下のみ許可。富岳は実HOME(`/vol0004/...`)と symlink(`/home/...`) があるため、両方を列挙するとよい。

### 3. ジョブ資源上限（submit_job）
- ノード数・経過時間・リソースグループの上限/許可リストを強制。

## 監査ログ
`FUGAKU_AUDIT_LOG=/path/to/audit.jsonl` を設定すると、全ツール呼び出しを1行JSONで記録:
```json
{"ts":"2026-06-28T22:10:00+0900","tool":"run_command","args":{"command":"ls -la"},"ok":true,"note":""}
```
ポリシー違反は `ok:false` と理由（`note`）付きで記録される。

## 推奨設定例
- **個人PoC（現状）**: 既定のまま（denylist）。必要なら `FUGAKU_AUDIT_LOG` を有効化。
- **共有/サービス化**: `FUGAKU_CMD_MODE=allowlist`、`FUGAKU_PATH_ROOTS` で各ユーザHOMEに限定、`FUGAKU_ALLOWED_RSCGRP`/`FUGAKU_MAX_*` で資源制限、`FUGAKU_AUDIT_LOG` 必須。
