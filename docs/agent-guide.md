日本語 | [English](agent-guide.en.md)

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

## ジョブ配列（バルクジョブ）・依存ジョブ（ステップジョブ）
パラメータサーベイや依存関係のあるジョブ列は pjsub の機能で実現できる。**どちらも `run_job` は使わず
`submit_job`（低レベル）＋ `extra_qopt` で投入する**（run_job は全出力を単一の `<name>.result` に集約するため、
複数サブジョブが同じファイルへ書いて衝突する）。

### バルクジョブ（同じスクリプトをパラメータ違いで多数実行）
- 投入: `submit_job(script=..., extra_qopt='--bulk --sparam "0-9"')` → バルク番号 0〜9 の10サブジョブ（範囲は 0〜999999）。
- スクリプト内では環境変数 `${PJM_BULKNUM}` で自分の番号を参照し、入出力を分ける:
  ```bash
  #!/bin/bash
  ./a.out < indata.${PJM_BULKNUM} > outdata.${PJM_BULKNUM} 2>&1
  ```
- サブジョブIDは「ジョブID[バルク番号]」形式（例 `12345[1]`）。状態は `run_command("pjstat")` で確認。
- `nodes`/`elapse` は**サブジョブ1個あたり**の指定。ノード時間は サブジョブ数×nodes×elapse 消費される点に注意。

### ステップジョブ（依存関係のある逐次実行）
- 1本目: `submit_job(script=..., extra_qopt='--step')` → 応答例 `Job 71080_0 submitted`（サブジョブID=「ジョブID_ステップ番号」）。
- 2本目以降は `jid=` で同じステップジョブに連結:
  `extra_qopt='--step --sparam "jid=71080"'`（前のサブジョブ終了後に実行される）。
- 依存条件は `sd=`（依存関係式）で指定。例: `--sparam "jid=71080,sd=ec!=0:one:1"`
  = 「サブジョブ1の終了コード(ec)が0以外なら、このサブジョブを削除(one)する」。
- 完了確認は `job_status(ジョブID部分)` か `run_command("pjstat")`。詳細書式は `search_manual("ステップジョブ")`。

## コンパイル（ログインノードで run_command）
- **コンパイルは必ずログインノードで、クロスコンパイラを使って行う**（計算ノードやジョブ内ではビルドしない）。`run_command` はログインノード上で動くので、ビルドは `run_command` で実行し、実行（`./a.out`）だけを `run_job` で計算ノードに投げる。
- 富士通コンパイラ（A64FX最適化）: C=`fcc` / C++=`FCC` / Fortran=`frt`。MPI版=`mpifcc` / `mpiFCC` / `mpifrt`。いずれもログインノード上で計算ノード向けにクロスコンパイルする。
- GCC等のクロスコンパイルも可。環境切替は `module`（や `spack`）。
- 例: `run_command("mpifcc -Kfast -o a.out main.c")`、`run_command("module avail")`。
- 正確なオプション・最適化（`-Kfast` 等）は公式「言語開発環境編」を参照。

## Spack（OSS・ライブラリの導入）
富岳ではOSSパッケージ管理に Spack が整備されている（パブリック・インスタンス=導入済みパッケージ群）。
- 環境設定（bash）: `. /vol0004/apps/oss/spack/share/spack/setup-env.sh`
  （`.bashrc` には書かないこと=ファイルシステム障害時にログイン不能になる恐れ）
- 導入済みパッケージ一覧: `spack find -x` ／ 利用: `spack load <pkg>`（例 `spack load tmux`）／ 解除: `spack unload <pkg>`
- 同名パッケージが複数あるときは版・コンパイラ・ハッシュで特定: `spack load screen@4.9.1`、`spack load screen%fj`、`spack load /e754igt`
- **ジョブ内（計算ノード）で使う場合は `-x PJM_LLIO_GFSCACHE=/vol0004` が必須**（Spack本体が /vol0004 にあるため）:
  `run_job(commands=". /vol0004/apps/oss/spack/share/spack/setup-env.sh && spack load <pkg> && ./a.out", extra_qopt='-x PJM_LLIO_GFSCACHE=/vol0004')`
- 既知の問題: `spack load` 後にコマンドが動かない → `export LD_LIBRARY_PATH=/lib64:$LD_LIBRARY_PATH` で回復することがある。
- 詳細は公式「Fugaku Spack Guide」（末尾リンク）。

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

## パス・ファイル・ストレージ（LLIO）
- ファイルAPIは**絶対パス**。`~` は展開されない（`run_command` 内では展開される）。一覧は `run_command("ls -la <dir>")`。
- ストレージ階層: `/home`（グループ領域・小容量）、大容量データは**第2階層 `/vol000N`**（FEFS）。
  計算ノード直近の高速IOは**第1階層（LLIO）**が担う。
- **ジョブから `/vol000N` を読み書きするときは `-x PJM_LLIO_GFSCACHE=/vol000N` を指定**（第2階層キャッシュの対象ボリューム指定。
  `run_job` では `extra_qopt='-x PJM_LLIO_GFSCACHE=/vol0004'` のように渡す）。
- LLIOの内訳: ノード当たり約87GiBを「ノード内テンポラリ領域＋共有テンポラリ領域＋第2階層キャッシュ」で分け合う
  （キャッシュは最低128MiB必要）。サイズは pjsub `--llio localtmp-size=10Gi` / `--llio sharedtmp-size=10Gi` 等で指定（`extra_qopt` で渡す）。
- **大規模ジョブで全ノードが同じファイル（実行ファイル・入力）を読むときは `llio_transfer ./a.out`** で事前配布するとアクセス集中を回避できる
  （読み取り専用・ジョブスクリプト内で実行、終わったら `llio_transfer --purge`）。
- 注意: `--llio async-close=on` 使用時、ノード障害やジョブ時間超過では書出し完了が保証されない。詳細は公式「8. 階層化ストレージ」。

## 性能分析・チューニング
- まず `#PJM -S`（`extra_qopt='-S'`）でジョブ統計（ノード・メモリ使用等）を出力し、`elapse` 実測と合わせて資源量を見直す。
- コンパイル最適化: 富士通コンパイラは `-Kfast` が基本。スレッド並列は `-Kopenmp`（OpenMP）。ノード内48コアの使い切りは
  「フラットMPI（48プロセス/ノード）」か「MPI＋OpenMPハイブリッド（例 4プロセス×12スレッド、`export OMP_NUM_THREADS=12`）」。
- プロファイラ（富士通 Development Studio、ログインノードから利用可）:
  - 簡易プロファイラ fipp: ジョブ内で `fipp -C -d ./fipp_out mpiexec ./a.out` → ログインノードで `fipppx -A -d ./fipp_out`（コスト分布・MPI待ち等）。
  - 詳細プロファイラ fapp: `fapp -C -d ./fapp_out mpiexec ./a.out` → `fapppx -A -d ./fapp_out`。CPU性能解析レポート（PA情報）は
    `-Hevent=pa1`〜の複数回測定＋公式Excel（cpu_pa_report.xlsm）で可視化。
  - PAPI によるハードウェアカウンタ取得も可（言語開発環境編 6章）。
  - 詳細は公式マニュアル一覧の「プロファイラ使用手引書」。

## それでも分からないとき
- **このガイド(`fugaku_help`)に無い情報は `search_manual(query)` で公式マニュアルを検索**して範囲を広げる（該当箇所の抜粋とURLが返る。`lang="en"` で英語）。
- `run_command` で `module avail`・`pjacl`・`pjstat`・`ls` 等を実行し、環境・資源・ファイルを実地に調べる。
- 公式ユーザガイド／生成AIチャット AskDona（富岳サポートサイト）を参照（将来エージェント連携を予定）。

## 公式マニュアル
- 利用およびジョブ実行編: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-use-1.52/build/ja/index.html
  （5.3 ステップジョブ / 5.4 バルクジョブ / 8. 階層化ストレージ・LLIO を含む）
- 言語開発環境編（コンパイラ・PAPI）: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-lang-1.41/build/ja/index.html
- Fugaku Spack Guide: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/fugakuspackguide/build/ja/index.html
- スタートアップガイド / マニュアル一覧（プロファイラ使用手引書ほか）: https://www.r-ccs.riken.jp/fugaku/user-manuals/
- リソースグループ構成: https://www.fugaku.r-ccs.riken.jp/resource_group_config
