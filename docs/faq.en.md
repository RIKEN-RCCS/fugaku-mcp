[日本語](faq.md) | English

# FAQ & Troubleshooting

## Setup & Authentication
**Q. Do I need a VPN?**
No. The Fugaku WebAPI is exposed on the public internet and authenticates with an X.509 certificate.

**Q. I forgot my certificate passphrase / my certificate has expired.**
Reissue the certificate from the HPCI/R-CCS portal, then re-run `./setup_user.sh new-certificate.p12`.

**Q. I want to use this across multiple projects.**
Place a `.mcp.json` in each folder you work in, and it will take effect when you start in that folder ([QUICKSTART](../QUICKSTART.en.md)).

**Q. Can I use this on Windows?**
Yes — **inside WSL2**. The setup scripts assume bash, `openssl`, and `curl`. See
["Using it on Windows (WSL2)" in QUICKSTART](../QUICKSTART.en.md). Copy your certificate from `/mnt/c/...`
**into your WSL2 home before using it** (permissions do not apply under `/mnt/c`, so your private key cannot
be protected there). Your AI client must run inside WSL2 too. Native Windows is not yet verified.

**Q. `python3 -m venv` or `pip install "mcp[cli]~=2.0"` fails.**
Python 3.10 or later is required. If 3.14 fails, try 3.12 (`python3.12 -m venv .venv`).

**Q. It won't start, failing with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`.**
MCP SDK 2.0.0 (released 2026-07-28) renamed the `FastMCP` class to `MCPServer`. This repository supports
both 1.x and 2.x, so **updating the code** resolves it (`./update.sh` or `git pull`). If you must stay on an
older revision of the code, pin with `pip install "mcp[cli]<2"` instead.

## Tools Don't Appear / Changes Aren't Applied
**Q. The `fugaku` tools don't show up in Claude Code.**
1. **Fully quit and restart (Cmd+Q)** before relaunching (closing the window with the X or Cmd+W is not enough).
2. Confirm there is a `.mcp.json` directly inside the folder you are using.
3. Confirm you allowed the "Allow `fugaku`?" prompt at startup.

**Q. I changed my settings or code, but nothing changes.**
- **Adding or removing tools** (e.g. a new tool) → a **full restart (Cmd+Q)** is required.
- Changing environment variables → likewise applied after a restart.

**Q. I want to verify my configuration is correct.**
Ask "Show me my account info on Fugaku" (`account_info`) to check the account, HOME, and group being used.

## Jobs
**Q. My job is rejected.**
This is often caused by the resource group / billing group you specified. Specify it like "use the XYZ group," "use rscgrp small," or "1 node for 5 minutes." Resource limits (number of nodes, time) may be restricted by policy ([security.en.md](security.en.md)).

**Q. Submission is slow / takes tens of seconds.**
This is normal. Job submission runs synchronously on the Fugaku side, so it takes time. `run_job` waits until completion.

**Q. I can't see my job results.**
- If you use `run_job`, results are collected automatically. To do it manually, ask "Show me `~/mcp-jobs/<name>.result`."
- Completed jobs disappear from the run queue, and the history (sacct) only covers the **last 24 hours**. For older results, retrieve the job output files with `stage_out`.

**Q. A long job exceeded the wait time.**
When the wait time is exceeded, `run_job` returns a jobid. Check it with "What is the status of job XYZ?" (`job_status`), and once it finishes, ask "Show me the result" (`fetch_result`).

## Files
**Q. How do I specify a file path?**
Use an **absolute path**. The file-operation APIs do not expand `~` (tilde) (command execution does expand it).

**Q. Can I overwrite existing files?**
`stage_in` automatically overwrites existing files.

## Safety Policy & Permissions
**Q. A command was denied.**
Dangerous commands are denied by the safety policy. Control the allowed scope with `FUGAKU_CMD_MODE` (denylist/allowlist) ([security.en.md](security.en.md)).

**Q. Can I see other people's files or jobs?**
No. Operations are **confined to your own account's permissions** (isolated at Fugaku's OS level). Reading from or writing to system/other users' areas is denied.

## Privacy & Data Flow (Important)
**Q. Where do file contents and job results go?**
Traffic between your PC ↔ the Fugaku WebAPI is over HTTPS (certificate authentication). However, **any content the AI assistant reads (file contents, job output, etc.) is sent to the AI model (cloud) to generate its responses**. When handling sensitive data, avoid unnecessarily passing contents to the agent via `stage_out` or `cat`.

**Q. Can compute nodes reach the internet?**
No. The AI (the brain) runs locally, while the Fugaku side focuses solely on running computations. The two are connected through certificate-secured HTTPS API calls (see the architecture in the [README](../README.en.md)).

## Updating
**Q. `./update.sh` fails with `error: unknown option 'ff-only'`.**
This is a bug in `update.sh` before 1.6.2. Since `update.sh` runs the old copy already on your machine, it dies
before it can fetch the fixed version. Update manually, once (no need to reinstall dependencies):
```bash
cd /path/to/fugaku-mcp && git pull --ff-only
```
Once you are on 1.6.2 or later, `./update.sh` works normally. See [updating.en.md](updating.en.md).

## History & Operations
**Q. I want to keep a usage log.**
Set `FUGAKU_AUDIT_LOG` for local logging and `FUGAKU_AUDIT_REMOTE` for aggregation on Fugaku. Aggregate with `tests/audit_report.py` ([multi-user.en.md](multi-user.en.md)).

## When That Still Doesn't Solve It
- Re-run `./setup_user.sh <certificate>.p12` to isolate connectivity issues (authentication, network).
- Check whether "Show me the status of Fugaku" works (= connection OK) as a starting point.
- Share any unknown error messages with your administrator or the developers.
