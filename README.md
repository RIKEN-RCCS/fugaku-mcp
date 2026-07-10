日本語 | [English](README.en.md)

# fugaku-mcp

スーパーコンピュータ「富岳」を **AIエージェント（Claude Code 等）から自然言語で操作**できるようにする
MCP（Model Context Protocol）サーバ。富岳の公式 REST WebAPI（X.509証明書認証）をラップし、
ジョブ投入・監視・ファイル転送・状態確認をエージェントのツールとして公開する。

> Claude Code に「富岳で hostname と date を出すジョブを投げて結果を見せて」と指示するだけで、
> ジョブ投入 → ステータス監視 → 結果回収まで全自動で実行できる。

**▶ はじめて使う方は [QUICKSTART.md](QUICKSTART.md)（5分で使い始められます）**

## アーキテクチャ

```
[AIエージェント / Claude Code]  --MCP-->  [fugaku_mcp.py]  --REST/X.509-->  富岳WebAPI  -->  富岳
       LLM=頭脳                      薄いMCPアダプタ          (R-CCS公式)         ジョブ実行
```

LLM本体は手元（ローカル）で動き、富岳側は計算の実行に専念する。両者は証明書付きHTTPSのAPI呼び出しでつながる。
**MCPサーバを含め、このツールはすべて利用者のローカルで動作する**（富岳側に常駐プロセスは置かない）。

## 構成
| パス | 内容 |
|---|---|
| `fugaku_api.py` | 富岳WebAPIクライアント（標準ライブラリのみ・依存ゼロ） |
| `fugaku_mcp.py` | MCPサーバ本体（依存は `mcp` のみ）・本人情報の自動検出・更新チェック |
| `fugaku_policy.py` | 安全策ポリシー（コマンド許可/拒否・パス制限・資源上限・監査） |
| `setup_user.sh` | オンボーディング（p12→pem・疎通確認・.mcp.json生成） |
| `tests/` | スモークテスト・監査集計（`audit_report.py`） |
| `docs/` | [使い方カタログ](docs/usage-catalog.md) / [エージェント運用ガイド](docs/agent-guide.md) / [FAQ](docs/faq.md) / [対応クライアント](docs/clients.md) / [更新](docs/updating.md) / [多ユーザー運用](docs/multi-user.md) / [安全策ポリシー](docs/security.md) |

## 公開ツール
| ツール | 説明 |
|---|---|
| `cluster_status` | 富岳(computer)の稼働状態 |
| `account_info` | 接続に使われる本人情報（アカウント/HOME/グループ。自動検出）|
| `list_jobs` | 自分のジョブ一覧（実行中 / 完了済み直近24h） |
| `run_job` | 投入→完了待ち→標準出力の自動回収を一括（最も手軽）|
| `submit_job` | バッチジョブ投入（低レベル）。jobidを返す |
| `fetch_result` | `run_job` の結果ファイルを取得 |
| `job_status` | 状態確認（実行中→active / 完了→sacct照合）|
| `cancel_job` | ジョブ取消(pjdel) |
| `stage_in` / `stage_out` | 富岳へ/から ファイル転送 |
| `run_command` | ログインノードで軽量コマンド実行（ポリシー検査つき）|
| `check_update` | fugaku-mcp の更新があるか確認（[更新](docs/updating.md)）|
| `fugaku_help` | 富岳の使い方・よくあるエラー対処を返す（[ガイド](docs/agent-guide.md)）|

## セットアップ（要点）

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp[cli]"
openssl pkcs12 -in <account>.p12 -nodes -out <account>.pem   # cert+key 結合PEM

# 設定は証明書パスのみ必須（HOME/アカウント/グループは起動時に自動検出）
export FUGAKU_CERT=/path/to/<account>.pem
python test_client.py          # ツール一覧 + cluster_status で確認

# 新規ユーザーのオンボーディングは ↓（p12→pem・疎通確認・.mcp.json生成）
./setup_user.sh <account>.p12
```

詳細な手順は [QUICKSTART.md](QUICKSTART.md)、複数人運用は [docs/multi-user.md](docs/multi-user.md) を参照。

## プラグインとして導入（/plugin・手編集不要）
Claude Code では marketplace 経由でも導入できます（`.mcp.json` の手編集が不要）:
```
/plugin marketplace add RIKEN-RCCS/fugaku-mcp
/plugin install fugaku@fugaku-mcp
```
- 導入後 `/fugaku:setup` で証明書を配置（`.p12`→`.pem` 変換して `~/.fugaku/fugaku.pem` へ）。`/reload-plugins` か再起動で有効化。
- Python依存(`mcp`)は初回起動時に自動用意されます（`plugin-run.sh` が venv を作成）。**Python 3.10+ が必要**。
- 証明書のみ各自で用意（HPCI/R-CCS 発行）。

## 前提
- 富岳のアカウントと X.509 クライアント証明書（HPCI/R-CCS のポータルで発行）
- Python 3.10+（3.14で `mcp` 導入に難があれば 3.12 推奨）、Claude Code
- 富岳WebAPIへ到達できるネットワーク（VPN不要）

## セキュリティ
- **証明書（`*.pem` / `*.p12`）や秘密鍵・トークンは絶対にコミットしない**（`.gitignore` で除外済み）。
- 安全策ポリシー（コマンド許可/拒否・パス制限・資源上限・監査ログ）を環境変数で制御。詳細は [docs/security.md](docs/security.md)。
- 操作は富岳側で**利用者のアカウント権限に閉じる**（OSレベルで分離）。
- 注意: AIアシスタントが読み取った内容（ファイル本文・ジョブ出力）は応答生成のためAIモデルに送られる。機微データの取り扱いに注意（[docs/faq.md](docs/faq.md)）。

## ライセンス
[MIT License](LICENSE)
