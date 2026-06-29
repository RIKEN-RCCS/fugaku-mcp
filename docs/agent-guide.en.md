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

## Compilation (run_command on the login node)
- Fujitsu compilers (A64FX optimized): C=`fcc` / C++=`FCC` / Fortran=`frt`. MPI versions=`mpifcc` / `mpiFCC` / `mpifrt`.
- Cross-compilation with GCC and others is also possible. Switch environments with `module` (or `spack`).
- Examples: `run_command("mpifcc -Kfast -o a.out main.c")`, `run_command("module avail")`.
- For exact options and optimizations (`-Kfast`, etc.), refer to the official "Language and development environment".

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

## Paths, files, storage
- The file API uses **absolute paths**. `~` is not expanded (it is expanded within `run_command`). List with `run_command("ls -la <dir>")`.
- Storage: `/home` (group area); for large capacity use the second tier `/vol...` (FEFS). High-speed I/O for jobs uses LLIO. For details, see the "Programming Guide (I/O)".

## When you still can't figure it out
- Use `run_command` to run `module avail`, `pjacl`, `pjstat`, `ls`, etc. to inspect the environment, resources, and files in practice.
- Refer to the official user guide / the generative AI chat AskDona (Fugaku support site) (agent integration is planned for the future).

## Official manuals
- Use and job execution: https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-use-1.52/build/en/index.html
- Language and development environment (compilers): https://riken-rccs.github.io/fugaku-doc/docs/user-guide/sys-use/user-guide-lang-1.41/build/en/index.html
- Startup guide / manual list: https://www.r-ccs.riken.jp/en/fugaku/user-manuals/
- Resource group configuration: https://www.fugaku.r-ccs.riken.jp/resource_group_config
