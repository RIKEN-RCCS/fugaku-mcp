[日本語](security.md) | English

# Safety Policy (Phase 2)

The MCP server's safety policy is consolidated in [`fugaku_policy.py`](../fugaku_policy.py) and is entirely controlled through environment variables.
This lets you tighten the controls without code changes, and is designed to be extended to per-user policies when moving to a site-wide service.

## Configuration (Environment Variables)

| Variable | Default | Description |
|---|---|---|
| `FUGAKU_CMD_MODE` | `denylist` | Mode for `run_command`: `denylist` / `allowlist` / `off` |
| `FUGAKU_ALLOW_CMDS` | default set | Executables permitted in allowlist mode (comma- or whitespace-separated) |
| `FUGAKU_PATH_ROOTS` | (none) | Path prefixes for which file operations are permitted (`:`-separated). Example: `/home/<account>:/vol0004/<group>/<account>` |
| `FUGAKU_MAX_NODES` | `8` | Maximum number of nodes for `submit_job` |
| `FUGAKU_MAX_ELAPSE_SEC` | `86400` | Maximum elapsed time for `submit_job` (seconds) |
| `FUGAKU_ALLOWED_RSCGRP` | (none) | Permitted resource groups (comma-separated) |
| `FUGAKU_MAX_BULK` | (none) | Maximum number of sub-jobs in a bulk job (`--sparam "0-9"` counts as 10) |
| `FUGAKU_LOCAL_ROOTS` | (none) | Directories on **your machine** that `stage_in`/`stage_out` may read or write (`:`-separated on macOS/Linux, `;` on Windows) |
| `FUGAKU_AUDIT_LOG` | (none) | Path to the local audit log. When set, all tool calls are appended as JSONL |
| `FUGAKU_AUDIT_REMOTE` | (none) | Audit aggregation directory on Fugaku. Appended asynchronously and in batches to `<dir>/<account>.jsonl` (for collecting multi-user history) |

## Three Layers of Defense

### 1. Command Inspection (run_command)
- **denylist (default)**: Always rejects clearly destructive patterns (recursive-and-forced `rm` in any spelling — `-rf`/`-Rf`/`-r -f`/`--recursive --force`, including `xargs rm -rf` and `find -exec rm -rf` — fork bombs, `mkfs`/`dd`/`shred`, `shutdown`, and the network-to-shell pipe `curl|sh`). A pragmatic default intended for use with your own account as a single user.
- **allowlist (strict)**: Permits only the default set of safe commands (read, inspection, and build operations). Each segment of a command chain (`;`, `&&`, `|`, etc.) is inspected, and command substitution `$()` / `` ` `` is uniformly rejected. `pjsub`/`pjdel` are intentionally not permitted (forcing use via `submit_job`/`cancel_job` so that resource limits apply). Intended for service deployment and shared environments.
- The denylist is always applied as well, even in allowlist mode.

> Note: Shells are highly expressive, and the allowlist's chain parsing is best-effort. True isolation requires a server-side restricted shell, which remains future work.

### 2. Path Restriction (stage_in / stage_out / fetch_result)
- **On Fugaku**: rejects paths containing `..` (to prevent traversal); absolute paths are required. When `FUGAKU_PATH_ROOTS` is set, only paths under those roots are permitted. Because Fugaku has both a real HOME (`/vol0004/...`) and a symlink (`/home/...`), it is best to list both. The job name given to `fetch_result` is validated too (alphanumerics and `. - _ @` only), so it cannot read outside the job directory.
- **On your machine**: files and directories that are hidden (`~/.ssh`, the certificate in `~/.fugaku`, various settings) are **always refused for reading and writing, regardless of configuration**. This prevents an agent that has been steered by instructions planted in a document on Fugaku from overwriting or exfiltrating your local keys. Symbolic links are resolved before the check. When `FUGAKU_LOCAL_ROOTS` is set, access is further limited to those directories.
- `stage_in` requires exactly one of `content` or `local_path` (preventing the accident of truncating an existing file to 0 bytes when both are empty).

### 3. Job Resource Limits (submit_job / run_job)
- Enforces upper limits / allowlists for node count, elapsed time, and resource group.
- **Preventing bypass**: `extra_qopt` may not set `node`, `elapse`, `rscgrp` or `rscunit` via `-L`/`--rsc-list`, the billing group (`-g`/`--gname`), or the job name (`-N`/`--name`) — these must come from the dedicated arguments. `#PJM` directives in a job script are **allowed if they match the arguments and rejected if they differ** (so the result does not depend on how directives and command-line options take precedence). When `FUGAKU_MAX_BULK` is set, the number of bulk sub-jobs is limited as well.

## Audit Log
Setting `FUGAKU_AUDIT_LOG=/path/to/audit.jsonl` records all tool calls as one-line JSON:
```json
{"ts":"2026-06-28T22:10:00+0900","tool":"run_command","args":{"command":"ls -la"},"ok":true,"note":""}
```
Policy violations are recorded with `ok:false` and the reason (`note`).

## Recommended Configuration Examples
- **Individual PoC (current state)**: Leave the defaults as-is (denylist). Enable `FUGAKU_AUDIT_LOG` if needed.
- **Shared / service deployment**: Set `FUGAKU_CMD_MODE=allowlist`, restrict to each user's HOME with `FUGAKU_PATH_ROOTS`, limit resources with `FUGAKU_ALLOWED_RSCGRP`/`FUGAKU_MAX_*` (including `FUGAKU_MAX_BULK`), restrict local read/write locations with `FUGAKU_LOCAL_ROOTS`, and require `FUGAKU_AUDIT_LOG`.
