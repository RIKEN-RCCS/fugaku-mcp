日本語 | [English](updating.en.md)

# 更新（アップデート）

fugaku-mcp は git で配布され、バージョンは `VERSION` で管理します。更新は **3層**で対応します。

## 1. 更新通知（既定）
- **起動時に自動チェック**し、新しい版があれば stderr に通知します（クライアントのログで確認可）。
- **`account_info`** に現在の版・更新の有無を併記（「富岳のアカウント情報を見て」で確認できる）。
- **`check_update` ツール**で能動確認（「fugaku-mcp に更新ある？」と話しかける）。
- チェック結果は24時間キャッシュ。ネットワーク失敗時は静かに無視（本処理は止めない）。

## 2. 手動更新（推奨）
リポジトリで更新スクリプトを実行:
```bash
cd /path/to/fugaku-mcp
./update.sh          # git pull --ff-only + 依存(mcp)更新
```
更新後は **MCPクライアント（Claude Code / Codex / vibe-local / opencode）を完全に再起動**して反映します
（ツールの増減がある場合は特に必須）。

## 3. 自動更新（オプトイン・要注意）
```json
"env": { "FUGAKU_AUTO_UPDATE": "1" }   # .mcp.json 等に設定
```
起動時に `update.sh`（git pull）を自動実行します。

> ⚠️ **注意**: 自動更新は、**あなたの富岳権限で動くコードを自動で取得・実行**することになります
> （リポジトリ侵害時のサプライチェーン・リスク）。共有・本番環境では既定（通知のみ＋手動更新）を推奨します。
> 自動更新でも、新コードの反映には次回のクライアント再起動が必要です。

**緩和策（update.sh に実装済み）**:
- `origin` が公式リポでなければ更新を中止（origin乗っ取り対策）。`git pull` は fast-forward のみ。
- **特定のタグ/コミットに固定**したい場合は `FUGAKU_UPDATE_REF` を設定（例 `FUGAKU_UPDATE_REF=v1.3.0`）。
  レビュー済みの ref に留めたい運用向け。設定時 `update.sh` はそのrefを `checkout` する。

## 環境変数
| 変数 | 説明 |
|---|---|
| `FUGAKU_NO_UPDATE_CHECK=1` | 更新チェックを無効化 |
| `FUGAKU_AUTO_UPDATE=1` | 起動時に自動更新（既定OFF・上記の注意参照）|
| `FUGAKU_UPDATE_URL` | 比較に使う VERSION の raw URL（既定は公開リポ main）|

## 管理者向け（リリース手順）
- 変更を main に反映する際、`VERSION` を更新（セマンティックバージョン）。利用者側の通知はこの `VERSION` 比較で出ます。
