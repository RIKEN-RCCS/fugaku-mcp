[日本語](agent-guide.md) | English

# Fugaku Agent Operations Guide (Basics and Troubleshooting)

This file is the knowledge base that the `fugaku_help` tool returns to the agent. It summarizes Fugaku's basic operations, job execution, compilation, MPI, and how to handle common errors. The source is the official Fugaku user manual (see "Official manuals" at the end).

## Basic workflow
- **`run_job` is the default for computation**: pass shell commands (`commands`) and it handles everything at once — "submit → wait for completion → automatically collect standard output (stdout+stderr)".
- Status checks: `cluster_status` (operation) / `list_jobs` (your own jobs) / `account_info` (account, HOME, group).
- Files: `stage_in` (send) / `stage_out` (retrieve). **Use absolute paths**.
- Light work on the login node (**compilation, checks, etc.**): `run_command`. **Always run heavy computation as a job (`run_job`)**.

## How to submit a job (run_job)
- Example: `run_job(commands="./a.out", name="run1", nodes=1, elapse="00:30:00", rscgrp="small")`
- `name`: must start with a letter; alphanumerics plus `. - _ @`; within 63 characters.
- `nodes`: number of nodes. 1 node = 48 compute cores (A64FX, aarch64).
- `elapse`: elapsed time limit `HH:MM:SS` (e.g. `00:30:00`). Keep it within the resource group's limit.
- `rscgrp`: resource group (described below). The billing group (`-g`) is set automatically from the `group` in `account_info`.
- `extra_qopt`: lets you pass additional `pjsub` options (e.g. `--mpi` for MPI).
- Output goes to `~/mcp-jobs/<name>.result`, with the body in the `result` return value. You can also retrieve it later with `fetch_result(name)`.
- **With run_job you do not need to write `#PJM` directives yourself** (node/rscgrp/elapse/-N/-g are added by the tool as `pjsub` arguments). Only if you want low-level control should you pass an entire script with `submit_job` or use `extra_qopt`.

## Resource group (rscgrp)
- A job specifies a resource group (default `small`). Options include `small` / `large` and others.
- **The available group names and limits (node count, elapsed time) differ by environment and project**. For the exact list, refer to the official
  "Resource group configuration" https://www.fugaku.r-ccs.riken.jp/resource_group_config,
  or check what you can use with `run_command("pjacl")`.
- Rule of thumb: the allocation method (mesh/torus, etc.) changes between 384 nodes or fewer and 385 nodes or more. Large-scale runs use the `large` family.

## Batch job script and #PJM (reference for submit_job / low-level use)
The official standard job script example (submit with `pjsub sample.sh`):
```bash
#!/bin/bash
#PJM -L "node=1"
#PJM -L "rscgrp=small"
#PJM -L "elapse=00:30:00"
#PJM -g groupname
#PJM -x PJM_LLIO_GFSCACHE=/vol000N   # When using the Spack/LLIO cache
#PJM -S                              # Output execution statistics
./a.out
```
- When using `run_job`, these `-L`/`-g`/`-N` are added automatically, so `commands` only needs **the execution command**.

## MPI parallel execution
- Launch with `mpiexec` inside the job script: basic syntax `mpiexec -n <total number of processes> ./a.out`.
- **Multi-node MPI**: reserve nodes with `run_job(nodes=N, ...)`, set `commands` to `mpiexec -n <total processes> ./a.out`,
  and add `extra_qopt='--mpi "proc=<total processes>"'` (the total number of processes = nodes × processes per node).
- Example: 2 nodes, 4 processes per node → `run_job(commands="mpiexec -n 8 ./a.out", nodes=2, elapse="00:30:00", rscgrp="small", extra_qopt='--mpi "proc=8"')`
- **Location of MPI output (important)**: Fujitsu MPI (PLE) writes each rank's standard output to `$HOME/output.<jobid>/*/*/stdout.*`.
  The `-std`/`-of` options are **ignored** (a `[WARN] PLE 0605` is emitted). The output does not appear in the job's standard output or in shell redirection.
  - `run_job` **automatically collects** this after completion and places it in the `mpi_output` return value (the directory is deleted after collection). Normally you should just use `run_job`.
  - When using `submit_job` (low-level), collect it yourself after completion with `run_command("cat $HOME/output.<jobid>/*/*/stdout.* | sort | uniq -c")`.
- For details such as MPMD and process placement (rank), see the official manual "6. Running MPI jobs".

## Job arrays (bulk jobs) and dependent jobs (step jobs)
Parameter surveys and dependent job chains are provided by pjsub features. **For both, use `submit_job`
(low-level) with `extra_qopt`, not `run_job`** (run_job funnels all output into a single `<name>.result`,
so multiple sub-jobs would write to the same file and collide).

### Bulk jobs (run the same script many times with different parameters)
- Submit: `submit_job(script=..., extra_qopt='--bulk --sparam "0-9"')` → 10 sub-jobs with bulk numbers 0–9 (range 0–999999).
- Inside the script, use the environment variable `${PJM_BULKNUM}` to identify each sub-job and separate its I/O:
  ```bash
  #!/bin/bash
  ./a.out < indata.${PJM_BULKNUM} > outdata.${PJM_BULKNUM} 2>&1
  ```
- Sub-job IDs have the form "jobid[bulknum]" (e.g. `12345[1]`). Check status with `run_command("pjstat")`.
- `nodes`/`elapse` apply **per sub-job**. Note that node-hours consumed = number of sub-jobs × nodes × elapse.

### Step jobs (sequential execution with dependencies)
- First step: `submit_job(script=..., extra_qopt='--step')` → response like `Job 71080_0 submitted` (sub-job ID = "jobid_stepno").
- Attach subsequent steps to the same step job with `jid=`:
  `extra_qopt='--step --sparam "jid=71080"'` (runs after the previous sub-job finishes).
- Dependency conditions use `sd=` (dependency expressions). Example: `--sparam "jid=71080,sd=ec!=0:one:1"`
  = "if sub-job 1's exit code (ec) is non-zero, delete (one) this sub-job".
- Check completion with `job_status(<jobid part>)` or `run_command("pjstat")`. For the full syntax, use `search_manual("step job")`.

## Compilation (run_command on the login node)
- **Always compile on the login node using cross-compilers** (do not build on compute nodes or inside jobs). `run_command` runs on the login node, so build with `run_command` and submit only the execution (`./a.out`) to compute nodes via `run_job`.
- Fujitsu compilers (A64FX optimized): C=`fcc` / C++=`FCC` / Fortran=`frt`. MPI versions=`mpifcc` / `mpiFCC` / `mpifrt`. All of these cross-compile on the login node targeting the compute nodes.
- Cross-compilation with GCC and others is also possible. Switch environments with `module` (or `spack`).
- Examples: `run_command("mpifcc -Kfast -o a.out main.c")`, `run_command("module avail")`.
- For exact options and optimizations (`-Kfast`, etc.), refer to the official "Language and development environment".

## Spack (installing OSS and libraries)
Fugaku provides Spack for OSS package management (the public instance = pre-installed package set).
- Environment setup (bash): `. /vol0004/apps/oss/spack/share/spack/setup-env.sh`
  (do **not** put this in `.bashrc` — it can make login impossible during filesystem trouble)
- List installed packages: `spack find -x` / use one: `spack load <pkg>` (e.g. `spack load tmux`) / release: `spack unload <pkg>`
- When multiple packages share a name, pin by version, compiler, or hash: `spack load screen@4.9.1`, `spack load screen%fj`, `spack load /e754igt`
- **When using Spack inside a job (compute node), `-x PJM_LLIO_GFSCACHE=/vol0004` is required** (Spack itself lives on /vol0004):
  `run_job(commands=". /vol0004/apps/oss/spack/share/spack/setup-env.sh && spack load <pkg> && ./a.out", extra_qopt='-x PJM_LLIO_GFSCACHE=/vol0004')`
- Known issue: commands fail after `spack load` → `export LD_LIBRARY_PATH=/lib64:$LD_LIBRARY_PATH` often recovers it.
- Details: the official "Fugaku Spack Guide" (link at the end).

## How to read job status
- **It is normal for submission (submit) to take tens of seconds on the server side** (synchronous execution).
- Once completed, the job disappears from the run queue. The final state (`EXT`=normal end, `CCL`=canceled, `ERR`=error) appears in the history. `job_status` determines this automatically.
- `list_jobs(completed=true)` shows jobs completed in the last 24 hours. For detailed status use `pjstat`; to cancel use `cancel_job` (=`pjdel`).

## Common errors and how to handle them
- **Job rejected / submit error**: review `rscgrp`, `nodes`, `elapse`, and the billing group. Be explicit, e.g. "rscgrp=small, 1 node, 30 minutes". If you exceed a resource limit, lower it. Check available groups with `pjacl`.
- **submit times out**: the submission may have succeeded. Check with `list_jobs` before resubmitting (**beware of duplicate submission**).
- **File returns 409**: the file already exists. `stage_in` overwrites, so this is usually not a problem.
- **Permission denied / IO Error**: an operation outside your permissions (another user's or a system area). This is a **normal rejection**. Operate under your own HOME.
- **Command rejected by the safety policy**: dangerous commands (`rm -rf`, etc.) are rejected by policy. Change your intent or stay within what is allowed.
- **"No Jobs."**: a **normal response** meaning zero jobs (not an error).
- **MPI process counts don't match**: verify consistency between the total in `mpiexec -n`, `--mpi proc=`, and `node`.

## Paths, files, storage (LLIO)
- The file API uses **absolute paths**. `~` is not expanded (it is expanded within `run_command`). List with `run_command("ls -la <dir>")`.
- Storage tiers: `/home` (group area, small capacity); large data lives on the **second tier `/vol000N`** (FEFS).
  Fast I/O close to the compute nodes is provided by the **first tier (LLIO)**.
- **When a job reads/writes `/vol000N`, specify `-x PJM_LLIO_GFSCACHE=/vol000N`** (selects the volume for the second-tier cache;
  with `run_job`, pass it as `extra_qopt='-x PJM_LLIO_GFSCACHE=/vol0004'`).
- LLIO breakdown: about 87 GiB per node shared among "node-local temporary + shared temporary + second-tier cache"
  (the cache needs at least 128 MiB). Sizes are set with pjsub `--llio localtmp-size=10Gi` / `--llio sharedtmp-size=10Gi` etc. (pass via `extra_qopt`).
- **When all nodes of a large job read the same file (executable, input), distribute it first with `llio_transfer ./a.out`** to avoid access congestion
  (read-only; run inside the job script; clean up with `llio_transfer --purge`).
- Caution: with `--llio async-close=on`, write-out completion is not guaranteed on node failure or elapsed-time overrun. Details: official "8. Layered storage".

## Performance analysis and tuning
- Start with `#PJM -S` (`extra_qopt='-S'`) to output job statistics (nodes, memory usage, etc.), and adjust resources against measured `elapse`.
- Compiler optimization: for Fujitsu compilers, `-Kfast` is the baseline; thread parallelism uses `-Kopenmp` (OpenMP). To use all 48 cores per node,
  choose "flat MPI (48 processes/node)" or "MPI + OpenMP hybrid (e.g. 4 processes × 12 threads, `export OMP_NUM_THREADS=12`)".
- Profilers (Fujitsu Development Studio, usable from the login node):
  - Instant profiler fipp: inside the job, `fipp -C -d ./fipp_out mpiexec ./a.out` → on the login node, `fipppx -A -d ./fipp_out` (cost distribution, MPI wait, etc.).
  - Advanced profiler fapp: `fapp -C -d ./fapp_out mpiexec ./a.out` → `fapppx -A -d ./fapp_out`. For the CPU performance analysis report (PA data),
    run multiple measurements with `-Hevent=pa1`… and visualize with the official Excel sheet (cpu_pa_report.xlsm).
  - Hardware counters are also available via PAPI (Language guide, ch. 6).
  - Details: "Profiler User's Guide" in the official manual list.

## When you still can't figure it out
- **For anything not in this guide (`fugaku_help`), use `search_manual(query)` to search the official manuals** and broaden the search (returns matching excerpts and URLs; `lang="en"` for English).
- Use `run_command` to run `module avail`, `pjacl`, `pjstat`, `ls`, etc. to inspect the environment, resources, and files in practice.
- Refer to the official user guide / the generative AI chat AskDona (Fugaku support site) (agent integration is planned for the future).

## Official manuals
- Use and job execution: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-use-1.52/build/en/index.html
  (includes 5.3 Step jobs / 5.4 Bulk jobs / 8. Layered storage & LLIO)
- Language and development environment (compilers, PAPI): https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-lang-1.41/build/en/index.html
- Fugaku Spack Guide: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/fugakuspackguide/build/en/index.html
- Startup guide / manual list (incl. Profiler User's Guide): https://www.r-ccs.riken.jp/en/fugaku/user-manuals/
- Resource group configuration: https://www.fugaku.r-ccs.riken.jp/resource_group_config
