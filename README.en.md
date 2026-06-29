[日本語](README.md) | English

# fugaku-mcp

An MCP (Model Context Protocol) server that lets you **operate the Fugaku supercomputer in natural language from an AI agent (such as Claude Code)**.
It wraps Fugaku's official REST WebAPI (X.509 certificate authentication) and exposes job submission, monitoring, file transfer, and status checks as agent tools.

> Just tell Claude Code "submit a job on Fugaku that prints hostname and date, then show me the result,"
> and it runs the whole flow automatically: job submission → status monitoring → result retrieval.

**▶ New here? Start with [QUICKSTART.en.md](QUICKSTART.en.md) (up and running in 5 minutes)**

## Architecture

```
[AI agent / Claude Code]  --MCP-->  [fugaku_mcp.py]  --REST/X.509-->  Fugaku WebAPI  -->  Fugaku
     LLM = the brain          thin MCP adapter        (R-CCS official)     job execution
```

The LLM itself runs locally (on your machine), while Fugaku focuses solely on executing computations. The two are connected via certificate-backed HTTPS API calls.
**This tool, including the MCP server, runs entirely on the user's local machine** (no resident process is placed on the Fugaku side).

## Components
| Path | Contents |
|---|---|
| `fugaku_api.py` | Fugaku WebAPI client (standard library only, zero dependencies) |
| `fugaku_mcp.py` | The MCP server itself (depends only on `mcp`); auto-detects the user's identity; update check |
| `fugaku_policy.py` | Safety policy (command allow/deny, path restrictions, resource limits, auditing) |
| `setup_user.sh` | Onboarding (p12→pem, connectivity check, .mcp.json generation) |
| `tests/` | Smoke tests, audit aggregation (`audit_report.py`) |
| `docs/` | [Usage catalog](docs/usage-catalog.en.md) / [Agent guide](docs/agent-guide.en.md) / [FAQ](docs/faq.en.md) / [MCP clients](docs/clients.en.md) / [Updating](docs/updating.en.md) / [Multi-user operation](docs/multi-user.en.md) / [Safety policy](docs/security.en.md) |

## Exposed tools
| Tool | Description |
|---|---|
| `cluster_status` | Operational status of Fugaku (computer) |
| `account_info` | Identity used for the connection (account / HOME / group; auto-detected) |
| `list_jobs` | Your job list (running / completed within the last 24h) |
| `run_job` | All-in-one: submit → wait for completion → automatically retrieve standard output (the simplest option) |
| `submit_job` | Batch job submission (low-level). Returns a jobid |
| `fetch_result` | Retrieve the result file of a `run_job` |
| `job_status` | Status check (running → active / completed → reconciled via sacct) |
| `cancel_job` | Cancel a job (pjdel) |
| `stage_in` / `stage_out` | File transfer to / from Fugaku |
| `run_command` | Run lightweight commands on the login node (with policy checks) |
| `check_update` | Check whether a fugaku-mcp update is available ([Updating](docs/updating.en.md)) |
| `fugaku_help` | Return Fugaku usage tips and common-error remedies, `lang="en"` for English ([guide](docs/agent-guide.en.md)) |

## Setup (essentials)

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp[cli]"
openssl pkcs12 -in <account>.p12 -nodes -out <account>.pem   # combined cert+key PEM

# Only the certificate path is required (HOME/account/group are auto-detected at startup)
export FUGAKU_CERT=/path/to/<account>.pem
python test_client.py          # verify: lists tools + cluster_status

# Onboard a new user with the script below (p12->pem, connectivity check, .mcp.json generation)
./setup_user.sh <account>.p12
```

For detailed instructions see [QUICKSTART.en.md](QUICKSTART.en.md); for multi-user operation see [docs/multi-user.en.md](docs/multi-user.en.md).

## Prerequisites
- A Fugaku account and an X.509 client certificate (issued via the HPCI / R-CCS portal)
- Python 3.10+ (if installing `mcp` is difficult on 3.14, 3.12 is recommended), Claude Code
- Network access that can reach the Fugaku WebAPI (no VPN required)

## Security
- **Never commit certificates (`*.pem` / `*.p12`), private keys, or tokens** (already excluded via `.gitignore`).
- The safety policy (command allow/deny, path restrictions, resource limits, audit logs) is controlled via environment variables. See [docs/security.en.md](docs/security.en.md) for details.
- Operations are **confined to the user's account privileges** on the Fugaku side (isolated at the OS level).
- Note: Content read by the AI assistant (file contents, job output) is sent to the AI model in order to generate responses. Take care when handling sensitive data ([docs/faq.en.md](docs/faq.en.md)).

## License
[MIT License](LICENSE)
