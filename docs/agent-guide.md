# 富岳エージェント運用ガイド（基本と困ったとき）

このファイルは `fugaku_help` ツールがエージェントへ返す知識ベース。富岳の基本操作・ジョブ実行・コンパイル・MPI・
よくあるエラーの対処をまとめる。出典は富岳公式ユーザマニュアル（末尾「公式マニュアル」参照）。

## 基本ワークフロー
- **計算は `run_job` が基本**: シェルコマンド（`commands`）を渡すと「投入→完了待ち→標準出力(stdout+stderr)を自動回収」まで一括。
- 状態確認: `cluster_status`（稼働）/ `list_jobs`（自分のジョブ）/ `account_info`（アカウント・HOME・グループ）。
- ファイル: `stage_in`（送る）/ `stage_out`（取る）。**パスは絶対パス**。
- ログインノードの軽作業（**コンパイル・確認等**）: `run_command`。**重い計算は必ずジョブ（`run_job`）で**。

## ジョブの投げ方（run_job）
- 例: `run_job(commands="./a.out", name="run1", nodes=1, elapse="00:30:00", rscgrp="small")`
- `name`: 英字始まり・英数と `. - _ @`・63文字以内。
- `nodes`: ノード数。1ノード = 48計算コア（A64FX, aarch64）。
- `elapse`: 経過時間上限 `HH:MM:SS`（例 `00:30:00`）。リソースグループの上限以内にする。
- `rscgrp`: リソースグループ（後述）。課金グループ(`-g`)は `account_info` の `group` が自動付与。
- `extra_qopt`: 追加の `pjsub` オプションを渡せる（MPIの `--mpi` 等）。
- 出力は `~/mcp-jobs/<name>.result`。戻り値 `result` に本文。後から `fetch_result(name)` でも取得可。
- **run_job では `#PJM` ディレクティブを自分で書かなくてよい**（node/rscgrp/elapse/-N/-g はツールが `pjsub` 引数で付与する）。低レベルに制御したい場合のみ `submit_job` でスクリプト全体を渡すか `extra_qopt` を使う。

## リソースグループ（rscgrp）
- ジョブはリソースグループを指定する（既定 `small`）。`small` / `large` などがある。
- **利用可能なグループ名と上限（ノード数・経過時間）は環境・課題により異なる**。正確な一覧は公式の
  「Resource group configuration」 https://www.fugaku.r-ccs.riken.jp/resource_group_config を参照、
  または `run_command("pjacl")` で自分が使える範囲を確認する。
- 目安: 384ノード以下と385ノード以上で割り当て方式（mesh/torus等）が変わる。大規模は `large` 系。

## バッチジョブスクリプトと #PJM（submit_job/低レベル時の参考）
公式の標準的なジョブスクリプト例（`pjsub sample.sh` で投入）:
```bash
#!/bin/bash
#PJM -L "node=1"
#PJM -L "rscgrp=small"
#PJM -L "elapse=00:30:00"
#PJM -g groupname
#PJM -x PJM_LLIO_GFSCACHE=/vol000N   # Spack/LLIOキャッシュ利用時
#PJM -S                              # 実行統計の出力
./a.out
```
- `run_job` を使う場合、これらの `-L`/`-g`/`-N` は自動付与されるので、`commands` には**実行コマンドだけ**書けばよい。

## MPI 並列実行
- ジョブスクリプト内で `mpiexec` で起動: 基本構文 `mpiexec -n <総プロセス数> ./a.out`。
- **複数ノードMPI**: `run_job(nodes=N, ...)` でノードを確保し、`commands` に `mpiexec -n <総プロセス> ./a.out`、
  さらに `extra_qopt='--mpi "proc=<総プロセス>"'` を付ける（総プロセス数はノード数×ノードあたりプロセス数）。
- 例: 2ノード・1ノード4プロセス → `run_job(commands="mpiexec -n 8 ./a.out", nodes=2, elapse="00:30:00", rscgrp="small", extra_qopt='--mpi "proc=8"')`
- **MPI出力の場所（重要）**: Fujitsu MPI(PLE)は各ランクの標準出力を `$HOME/output.<jobid>/*/*/stdout.*` に書き出す。
  `-std`/`-of` オプションは**無視される**（`[WARN] PLE 0605` が出る）。ジョブの標準出力やシェルのリダイレクトには乗らない。
  - `run_job` はこれを**完了後に自動回収**し、戻り値の `mpi_output` に入れる（回収後はディレクトリ削除）。通常は `run_job` を使えばよい。
  - `submit_job`（低レベル）を使う場合は、完了後に自分で `run_command("cat $HOME/output.<jobid>/*/*/stdout.* | sort | uniq -c")` で回収する。
- MPMD等の詳細・プロセス配置(rank)は公式マニュアル「6. MPIジョブの実行」を参照。

## コンパイル（ログインノードで run_command）
- 富士通コンパイラ（A64FX最適化）: C=`fcc` / C++=`FCC` / Fortran=`frt`。MPI版=`mpifcc` / `mpiFCC` / `mpifrt`。
- GCC等のクロスコンパイルも可。環境切替は `module`（や `spack`）。
- 例: `run_command("mpifcc -Kfast -o a.out main.c")`、`run_command("module avail")`。
- 正確なオプション・最適化（`-Kfast` 等）は公式「言語開発環境編」を参照。

## ジョブの状態の見方
- **投入(submit)はサーバ側で数十秒かかるのは正常**（同期実行）。
- 完了するとジョブは実行キューから消える。最終状態（`EXT`=正常終了、`CCL`=取消、`ERR`=エラー）は履歴に出る。`job_status` が自動判定。
- `list_jobs(completed=true)` は直近24時間の完了ジョブ。状態詳細は `pjstat`、取消は `cancel_job`（=`pjdel`）。

## よくあるエラーと対処
- **ジョブが却下 / submit エラー**: `rscgrp`・`nodes`・`elapse`・課金グループを見直す。「rscgrp=small・1ノード・30分」のように明示。資源上限超過なら下げる。利用可能グループは `pjacl` で確認。
- **submit がタイムアウト**: 投入は成功していることがある。`list_jobs` で確認してから再投入（**二重投入注意**）。
- **ファイルが 409**: 既存ファイル。`stage_in` は上書きするので通常問題なし。
- **Permission denied / IO Error**: 自分の権限外（他ユーザ/システム領域）への操作。**正常な拒否**。自分の HOME 配下で操作する。
- **コマンドが安全策で拒否**: 危険コマンド（`rm -rf` 等）はポリシーで拒否。意図を変えるか許可された範囲で。
- **"No Jobs."**: ジョブ0件の**正常応答**（エラーではない）。
- **MPIでプロセス数が合わない**: `mpiexec -n` の総数と `--mpi proc=` と `node` の整合を確認。

## パス・ファイル・ストレージ
- ファイルAPIは**絶対パス**。`~` は展開されない（`run_command` 内では展開される）。一覧は `run_command("ls -la <dir>")`。
- ストレージ: `/home`（グループ領域）、大容量は第2階層 `/vol...`（FEFS）。ジョブの高速IOは LLIO。詳細は「プログラミングガイド(IO編)」。

## それでも分からないとき
- `run_command` で `module avail`・`pjacl`・`pjstat`・`ls` 等を実行し、環境・資源・ファイルを実地に調べる。
- 公式ユーザガイド／生成AIチャット AskDona（富岳サポートサイト）を参照（将来エージェント連携を予定）。

## 公式マニュアル
- 利用およびジョブ実行編: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-use-1.52/build/ja/index.html
- 言語開発環境編（コンパイラ）: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-lang-1.41/build/ja/index.html
- スタートアップガイド / マニュアル一覧: https://www.r-ccs.riken.jp/fugaku/user-manuals/
- リソースグループ構成: https://www.fugaku.r-ccs.riken.jp/resource_group_config
