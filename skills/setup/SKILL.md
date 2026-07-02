---
name: setup
description: 富岳MCPプラグインの証明書セットアップ（p12→pem変換・配置・疎通確認）を行う
---

# 富岳MCP セットアップ

このプラグインは富岳の X.509 クライアント証明書を使う。証明書ファイルを**プラグインのデータ領域**に
`fugaku.pem`（PEM形式・鍵結合）として配置すれば動作する。以下を手伝うこと。

## 手順
1. ユーザーに証明書ファイルの場所を尋ねる（HPCI/R-CCSで発行した `.p12`、または変換済み `.pem`）。
2. **配置先（プラグインのデータ領域）を特定する**。次のいずれかで探す:
   - `ls -d ~/.claude/plugins/*/*fugaku*/data 2>/dev/null` / `find ~/.claude -type d -path '*fugaku*' -name data 2>/dev/null`
   - 見つからなければ `~/.claude` 配下で `fugaku` を含むプラグインのデータ用ディレクトリを探す。
   - 配置先ファイルは `<データ領域>/fugaku.pem`。
3. **PEMへ変換して配置**（`.p12` の場合。パスフレーズはユーザーに入力してもらう）:
   ```bash
   openssl pkcs12 -in <p12> -nodes -out <データ領域>/fugaku.pem
   chmod 600 <データ領域>/fugaku.pem
   ```
   既に PEM（cert+key 結合）なら、その場所へコピーして `chmod 600`。
4. Claude Code で `/reload-plugins`（または完全再起動）してMCPサーバを有効化。
5. **疎通確認**: `cluster_status` ツールを呼び、`{"status":"OK","machine":"computer"}` が返れば成功。
   併せて `account_info` で自分のアカウント/HOME/グループが正しいか確認する。

## 注意
- 証明書には秘密鍵が含まれる。**権限は 600**、共有・コミットは厳禁。
- うまく繋がらない場合は `/mcp` でサーバの接続状態・エラーを確認し、証明書パス・有効期限・ネットワーク（VPN不要）を点検する。
- 使い方やエラー対処は `fugaku_help` ツールを参照。
