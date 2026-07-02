---
name: setup
description: 富岳MCPプラグインの証明書セットアップ（p12→pem変換・配置・疎通確認）を行う
---

# 富岳MCP セットアップ

このプラグインは富岳の X.509 クライアント証明書を使う。証明書を **`~/.fugaku/fugaku.pem`**
（PEM形式・秘密鍵結合）に置けば動作する。以下を手伝うこと。

## 手順
1. ユーザーに証明書の場所を尋ねる（HPCI/R-CCS発行の `.p12`、または変換済み `.pem`）。
2. **PEMへ変換して配置**（`.p12` の場合。パスフレーズはユーザーが入力）:
   ```bash
   mkdir -p ~/.fugaku
   openssl pkcs12 -in <p12> -nodes -out ~/.fugaku/fugaku.pem
   chmod 600 ~/.fugaku/fugaku.pem
   ```
   既に PEM（cert+key 結合）なら `~/.fugaku/fugaku.pem` へコピーして `chmod 600`。
3. `/reload-plugins`（または `claude` を再起動）してMCPサーバを有効化。
4. **疎通確認**: `cluster_status` を呼び `{"status":"OK","machine":"computer"}` が返れば成功。
   `account_info` で自分のアカウント/HOME/グループも確認する。

## 注意
- 証明書には秘密鍵が含まれる。**権限は 600**、共有・コミットは厳禁。
- 別パスの証明書を使いたい場合は `~/.fugaku/fugaku.pem` にシンボリックリンクを張ってもよい。
- 繋がらない場合は `/mcp` で接続状態・エラーを確認（証明書パス・有効期限・ネットワークはVPN不要）。使い方は `fugaku_help` を参照。
