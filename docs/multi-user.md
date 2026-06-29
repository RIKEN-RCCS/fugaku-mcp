# 多ユーザー運用ガイド（方式A: 各ユーザーがローカルで実行）

各ユーザーが**自分のMacで自分のMCPサーバを、自分の証明書で**動かす方式。集中サーバ・認証情報の集中保管がなく、
最も低リスクで即運用できる。各自の操作は富岳側で**その人のアカウント権限に閉じる**（OSレベルで分離）。

```
[ユーザーXのMac] Claude Code → ローカルMCP(Xの証明書) ─┐
[ユーザーYのMac] Claude Code → ローカルMCP(Yの証明書) ─┼→ 富岳WebAPI（各自の権限で実行）
[ユーザーZのMac] Claude Code → ローカルMCP(Zの証明書) ─┘
```

## 新規ユーザーのオンボーディング

**必要な設定は「自分の証明書パス」だけ。** HOME・アカウント名・課金グループは起動時に証明書から自動検出される。

```bash
# 1) リポジトリを取得し、venvを用意（初回のみ）
git clone <repo> fugaku_mcp && cd fugaku_mcp
python3 -m venv .venv && .venv/bin/pip install "mcp[cli]"

# 2) オンボーディング補助（p12→pem変換・疎通確認・本人情報検出・.mcp.json出力）
./setup_user.sh ~/Downloads/<account>.p12

# 3) 出力された .mcp.json を使うプロジェクト直下に保存し、Claude Code を完全再起動(⌘Q)
```

確認: Claude Code で `account_info` を呼ぶ（または「富岳のアカウント情報を見て」）と、自動検出された
`account / home / group` が返る。多ユーザーで**取り違えが起きていないか**の確認に使う。

## 設定（環境変数）
| 変数 | 必須 | 説明 |
|---|---|---|
| `FUGAKU_CERT` | ◯ | cert+key 結合PEM のパス |
| `FUGAKU_HOME` | — | 未指定で自動検出（`$HOME`） |
| `FUGAKU_GROUP` | — | 未指定で自動検出（主グループ）。課金グループが主グループと異なる場合のみ明示 |
| `FUGAKU_ACCOUNT` | — | 未指定で自動検出（`id -un`）。監査ログに付与 |
| `FUGAKU_AUDIT_LOG` | — | ローカル監査ログ（JSONL）のパス |
| `FUGAKU_AUDIT_REMOTE` | — | 富岳上の監査集約ディレクトリ（`<dir>/<account>.jsonl` へ非同期追記）|
| その他 | — | `FUGAKU_RSCUNIT` / `FUGAKU_MAX_NODES` 等の安全策は [security.md](security.md) 参照 |

## 各ユーザーが守ること（セキュリティ）
- **証明書（`*.pem`/`*.p12`）は本人のMac内のみ**。共有・コミットしない（鍵盗難=本人権限の侵害）。ファイル権限は600。
- 端末紛失・離任時は**証明書の失効**を申請する。
- 安全策ポリシー（`run_command` の許可範囲・資源上限）は各自の `.mcp.json` の env で調整可（[security.md](security.md)）。
- 共有環境では `FUGAKU_AUDIT_LOG` を設定し操作を記録（アカウント名つきで残る）。

## 利用履歴の採取
方式Aは分散構成のため、履歴は「正本（富岳側）」と「エージェント詳細（富岳上に集約）」の二段で採る。

| 情報源 | 内容 | 正本性 |
|---|---|---|
| 富岳ジョブアカウンティング（`pjacct`）| ジョブ・資源・課金 | 高（R-CCS保持）|
| Kong アクセスログ | 全API呼び出し | 高（要R-CCS提供）|
| MCP監査ログ | エージェント操作の詳細 | 低（クライアント側）|

**MCP監査ログを富岳上に集約**するには、各ユーザーの `.mcp.json` の env に
`FUGAKU_AUDIT_REMOTE`（富岳上の共有ディレクトリ）を設定する。各操作が非同期・バッチで
`<dir>/<account>.jsonl` に追記される（ツールのレイテンシは増えない）。集計はこのディレクトリを読むだけ:

```bash
# 例: プロジェクト共有ディレクトリに集約
"FUGAKU_AUDIT_REMOTE": "/vol0004/<group>/<project>/mcp-audit"

# 集計レポート（ユーザー別・ツール別・日別）
python3 tests/audit_report.py --cert <pem> --remote /vol0004/<group>/<project>/mcp-audit
```

ローカル控え（`FUGAKU_AUDIT_LOG`）も併用すると、リモート送出失敗時の保険になる。
※方式Aのクライアント側ログは利用者が無効化でき**正本にはならない**。確実な統制ログが要件なら方式B。

## この方式でできないこと（将来の集中サービス＝方式Bが必要な範囲）
- 全ユーザー横断のクォータ・一元的な利用制限
- 中央での一括監査・異常検知
- → 必要になったら方式B（集中サービス・OIDC pass-through）を別途設計する。
