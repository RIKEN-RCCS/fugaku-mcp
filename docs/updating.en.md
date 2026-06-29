[日本語](updating.md) | English

# Updating

fugaku-mcp is distributed via git, with the version tracked in `VERSION`. Updates are handled in **three layers**.

## 1. Update notification (default)
- **Automatic check at startup**: if a newer version exists, a notice is printed to stderr (visible in the client's logs).
- **`account_info`** includes the current version and whether an update is available ("Show me my Fugaku account info").
- **`check_update` tool** for an explicit check (just ask "Is there an update for fugaku-mcp?").
- Results are cached for 24h. Network failures are ignored silently (the main flow never stops).

## 2. Manual update (recommended)
Run the update script in the repository:
```bash
cd /path/to/fugaku-mcp
./update.sh          # git pull --ff-only + dependency (mcp) update
```
After updating, **fully restart the MCP client (Claude Code / Codex / vibe-local)** to apply it
(especially required when the set of tools changes).

## 3. Auto-update (opt-in, use with care)
```json
"env": { "FUGAKU_AUTO_UPDATE": "1" }   // set in .mcp.json, etc.
```
Runs `update.sh` (git pull) automatically at startup.

> ⚠️ **Caution**: auto-update means **code that runs with your Fugaku privileges is fetched and executed
> automatically** (a supply-chain risk if the repository is compromised). For shared/production environments,
> prefer the default (notify only + manual update). Even with auto-update, a client restart is needed to load the new code.

## Environment variables
| Variable | Description |
|---|---|
| `FUGAKU_NO_UPDATE_CHECK=1` | Disable the update check |
| `FUGAKU_AUTO_UPDATE=1` | Auto-update at startup (off by default; see caution above) |
| `FUGAKU_UPDATE_URL` | Raw URL of the VERSION file to compare against (defaults to the public repo main) |

## For maintainers (release procedure)
- When merging changes into main, bump `VERSION` (semantic versioning). The user-side notification is driven by this `VERSION` comparison.
