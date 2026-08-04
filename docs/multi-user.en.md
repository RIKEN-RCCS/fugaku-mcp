[日本語](multi-user.md) | English

# Multi-User Operations Guide (Model A: Each User Runs Locally)

In this model, **each user runs their own MCP server on their own Mac, using their own certificate**. There is no central server and no centralized storage of credentials, making it the lowest-risk option that can be put into operation immediately. Each user's operations are **confined to that person's account permissions** on the Fugaku side (isolated at the OS level).

```
[User X's Mac] Claude Code → local MCP (X's certificate) ─┐
[User Y's Mac] Claude Code → local MCP (Y's certificate) ─┼→ Fugaku WebAPI (executed with each user's permissions)
[User Z's Mac] Claude Code → local MCP (Z's certificate) ─┘
```

## Onboarding a New User

**The only setting required is "your own certificate path."** HOME, account name, and billing/accounting group are auto-detected from the certificate at startup.

```bash
# 1) Clone the repository and set up a venv (first time only)
git clone <repo> fugaku_mcp && cd fugaku_mcp
python3 -m venv .venv && .venv/bin/pip install "mcp[cli]==2.0.0"

# 2) Onboarding helper (p12→pem conversion, connectivity check, identity detection, .mcp.json output)
./setup_user.sh ~/Downloads/<account>.p12

# 3) Save the generated .mcp.json directly under the project you want to use it in, then fully restart Claude Code (⌘Q)
```

Verification: In Claude Code, call `account_info` (or say "show me my Fugaku account info"), and it returns the auto-detected `account / home / group`. Use this to confirm that no **mix-up** has occurred in a multi-user setup.

## Configuration (Environment Variables)
| Variable | Required | Description |
|---|---|---|
| `FUGAKU_CERT` | ◯ | Path to the combined cert+key PEM |
| `FUGAKU_HOME` | — | Auto-detected if unspecified (`$HOME`) |
| `FUGAKU_GROUP` | — | Auto-detected if unspecified (primary group). Specify explicitly only when the billing/accounting group differs from the primary group |
| `FUGAKU_ACCOUNT` | — | Auto-detected if unspecified (`id -un`). Attached to the audit log |
| `FUGAKU_AUDIT_LOG` | — | Path to the local audit log (JSONL) |
| `FUGAKU_AUDIT_REMOTE` | — | Audit aggregation directory on Fugaku (asynchronously appended to `<dir>/<account>.jsonl`) |
| Other | — | For safeguards such as `FUGAKU_RSCUNIT` / `FUGAKU_MAX_NODES`, see [security.en.md](security.en.md) |

## What Each User Must Observe (Security)
- **Certificates (`*.pem`/`*.p12`) stay only on the owner's own Mac.** Do not share or commit them (key theft = compromise of that person's permissions). Set file permissions to 600.
- When a device is lost or a member leaves, request **revocation of the certificate**.
- The safeguard policy (the allowed scope of `run_command`, resource limits) can be adjusted per user via the env in each `.mcp.json` ([security.en.md](security.en.md)).
- In shared environments, set `FUGAKU_AUDIT_LOG` to record operations (they are retained with the account name attached).

## Collecting Usage History
Because Model A is a distributed configuration, usage history is collected in two tiers: the "authoritative record (on the Fugaku side)" and the "agent details (aggregated on Fugaku)."

| Source | Contents | Authoritativeness |
|---|---|---|
| Fugaku job accounting (`pjacct`) | Jobs, resources, billing | High (retained by R-CCS) |
| Kong access log | All API calls | High (must be provided by R-CCS) |
| MCP audit log | Details of agent operations | Low (client-side) |

To **aggregate the MCP audit log on Fugaku**, set `FUGAKU_AUDIT_REMOTE` (a shared directory on Fugaku) in the env of each user's `.mcp.json`. Each operation is appended asynchronously and in batches to `<dir>/<account>.jsonl` (without increasing tool latency). To tally, you only need to read this directory:

```bash
# Example: aggregate into a project shared directory
"FUGAKU_AUDIT_REMOTE": "/vol0004/<group>/<project>/mcp-audit"

# Aggregation report (by user, by tool, by day)
python3 tests/audit_report.py --cert <pem> --remote /vol0004/<group>/<project>/mcp-audit
```

Using a local copy (`FUGAKU_AUDIT_LOG`) alongside it provides a fallback in case remote transmission fails.
Note: Model A's client-side logs can be disabled by the user and therefore **are not authoritative**. If reliable, controlled logging is a requirement, use Model B.

## What This Model Cannot Do (Scope That Requires a Future Central Service = Model B)
- Cross-user quotas and centralized usage restrictions
- Centralized, consolidated auditing and anomaly detection
- → When these become necessary, design Model B (central service, OIDC pass-through) separately.
