[日本語](QUICKSTART.md) | English

# Quickstart — Using Fugaku from Your AI Assistant

Just by talking to your AI assistant, you can run jobs, manage files, and check status on Fugaku.
**Takes about 5 minutes.** No programming knowledge required.

**Claude Code, Codex, and opencode** are all supported (steps 1 and 2 are the same for everyone; only step 3 differs per client).

## 0. What you need beforehand

- A **Fugaku account** and an **X.509 client certificate (a `.p12` file)** (issued via the HPCI/R-CCS portal)
- One of the supported **AI clients**: [Claude Code](https://claude.com/claude-code) (desktop app or CLI),
  [Codex](https://developers.openai.com/codex), or [opencode](https://opencode.ai)
- **Python 3.10 or later**, plus `git` and `openssl` (standard on Mac/Linux; check with `python3 --version`)
- OS: **macOS / Linux**. On Windows, use **WSL2** (see "Using it on Windows" below)
- Network: **No VPN required** (the Fugaku WebAPI is publicly available on the internet and authenticates via certificate)

## 1. Installation (first time only)

```bash
# Get the tool and set up a dedicated Python environment
git clone https://github.com/RIKEN-RCCS/fugaku-mcp.git
cd fugaku-mcp
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]~=2.0"
```

> If installing `mcp` fails on Python 3.14, use 3.12 instead with `python3.12 -m venv .venv`.

## 2. Register your certificate (first time only)

Just hand over the `.p12` file you downloaded. Conversion, connectivity check, and configuration-file generation are all automated.

```bash
./setup_user.sh ~/Downloads/your-certificate.p12
```

- Partway through, you will be asked for the **certificate passphrase** (the one you set when the certificate was issued).
- On success, a **ready-to-paste `.mcp.json`** is displayed at the end.

## 3. Register with your AI client (first time only)

**Follow only the section for the client you use.** Every client needs the same **three things**
(all of them appear in the output of step 2).

| Setting | Value |
|---|---|
| Python to run | `<this repository>/.venv/bin/python` |
| Script to launch | `<this repository>/fugaku_mcp.py` |
| Environment variable `FUGAKU_CERT` | Path to the `.pem` created in step 2 |

> Your account name, HOME, and group are **auto-detected from the certificate at startup**, so the certificate path is the only thing you need to configure.

### Claude Code

1. Save the contents of the `.mcp.json` shown in step 2 as a file named `.mcp.json` **directly inside the folder (project) you use with Claude Code**.
2. **Fully restart Claude Code.**
   - Mac: bring the app to the front and press **⌘Q** (just closing the window with ✕ is not enough), then launch it again.
3. If you are prompted "Allow the MCP server `fugaku`?" on startup, choose **Allow**.

> If you use the `claude` CLI in a terminal, you can install it as a plugin instead (no hand-editing of `.mcp.json`):
> ```bash
> claude plugin marketplace add RIKEN-RCCS/fugaku-mcp
> claude plugin install fugaku@fugaku-mcp
> ```
> In that case, place your certificate at `~/.fugaku/fugaku.pem`.

### Codex

Add this to `~/.codex/config.toml` (note that it is **TOML**, not JSON):

```toml
[mcp_servers.fugaku]
command = "/path/to/fugaku-mcp/.venv/bin/python"
args = ["/path/to/fugaku-mcp/fugaku_mcp.py"]
env = { FUGAKU_CERT = "/path/to/your-certificate.pem" }
```

You can also register it from the command line:

```bash
codex mcp add fugaku \
  --env FUGAKU_CERT=/path/to/your-certificate.pem \
  -- /path/to/fugaku-mcp/.venv/bin/python /path/to/fugaku-mcp/fugaku_mcp.py
```

Restart Codex afterwards.

> **About approvals**: Codex asks for approval every time a tool runs. In the app, just allow it in the dialog
> that appears. Non-interactive `codex exec` auto-cancels approvals by default, so tools will not run there.

### opencode

Add this to `~/.config/opencode/opencode.json` (or `opencode.json` at the project root for a single project).
Note that **`command` combines the executable and its arguments into a single array**, and the
environment-variable key is **`environment`**, not `env`.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "fugaku": {
      "type": "local",
      "command": [
        "/path/to/fugaku-mcp/.venv/bin/python",
        "/path/to/fugaku-mcp/fugaku_mcp.py"
      ],
      "enabled": true,
      "environment": { "FUGAKU_CERT": "/path/to/your-certificate.pem" }
    }
  }
}
```

Restart opencode afterwards. The tools become available as `fugaku_<tool>`.

> Combined with a local LLM (Ollama), **nothing the AI reads leaves your machine**. See
> [docs/clients.en.md](docs/clients.en.md) for a configuration example.

> **Other clients** (vibe-local / Cursor / VS Code / Cline, etc.) → [docs/clients.en.md](docs/clients.en.md)

## Using it on Windows (WSL2)

The setup scripts (`setup_user.sh` / `update.sh`) assume bash, `openssl`, and `curl`, so on Windows please
run everything inside **WSL2 (Windows Subsystem for Linux)**. Steps 1–3 above work as-is inside WSL2.

```powershell
# In PowerShell (as Administrator), install WSL2 + Ubuntu, then start Ubuntu after rebooting
wsl --install -d Ubuntu
```

Inside Ubuntu (WSL2):

```bash
sudo apt update && sudo apt install -y python3-venv git openssl
```

From there, **follow step 1 onwards as normal**. A certificate you received on the Windows side is reachable
from WSL2 under `/mnt/c/...`.

```bash
# Example: using a certificate in your Windows Downloads folder
./setup_user.sh /mnt/c/Users/<your-windows-username>/Downloads/your-certificate.p12
```

> **Things to watch out for**
> - **Copy the certificate into your WSL2 home (`~/`) before using it.** Permissions do not behave as
>   expected under `/mnt/c/...`, so `chmod 600` cannot protect your private key there.
> - Run your AI client inside WSL2 as well (a Windows-side client cannot launch an MCP server that lives inside WSL2).
> - Every path in your configuration file must be a **WSL2 path** (e.g. `/home/<user>/fugaku-mcp/.venv/bin/python`).

> **About native Windows (without WSL)**: the MCP server itself is written using only the Python standard
> library, and CI (GitHub Actions on Windows) **verifies server startup, the MCP stdio connection, and
> line-ending/encoding handling every week**. However, **a live connection to Fugaku and use from a real AI
> client have not been verified yet**.
> If you try it, note that the venv path becomes `.venv\Scripts\python.exe`, and that you will need to convert
> the certificate manually (`openssl pkcs12 -in <cert>.p12 -nodes -out <cert>.pem`) in place of `setup_user.sh`.
> Reports of success or failure are welcome at [Issues](https://github.com/RIKEN-RCCS/fugaku-mcp/issues).

## 4. Verify it works

In a new conversation, try saying:

> Show me Fugaku's status

If you get a response like `{"status":"OK","machine":"computer"}`, it worked. Next:

> Show me my account information on Fugaku

→ Your account name, HOME, and group are displayed (handy for catching configuration mistakes).

## 5. Your first task

> Run `hostname` and `date` on Fugaku and show me the results

The AI submits a job behind the scenes, waits for it to complete, then retrieves and shows you the results.

## What you can do (example phrases)

| What you want to do | Example phrase |
|---|---|
| Operational status | "Show me Fugaku's status" |
| List your own jobs | "Do I have any running jobs?" / "Show me my recently finished jobs" |
| Run a job and retrieve results | "Run XYZ on Fugaku and show me the results" |
| Send/receive files | "Put this file on Fugaku" / "Fetch XYZ from Fugaku" |
| Lightweight commands | "Run `ls ~/` on Fugaku" |

## Troubleshooting

| Symptom | What to do |
|---|---|
| The `fugaku` tools don't appear | **Fully restart the client** (for the Claude Code desktop app, **⌘Q** — closing with ✕ or closing the window doesn't take effect). Check the config file's location and paths |
| Tools don't run in Codex | Check that you allowed it in the approval dialog. `codex exec` auto-cancels by default |
| Tools don't run in opencode | Check that `command` is a **single array** and the env key is **`environment`** |
| Authentication error / can't get status | Run `setup_user.sh` again to verify certificate connectivity. Also check whether the certificate has expired |
| "Certificate not found" | Check that the path in `FUGAKU_CERT` in `.mcp.json` is correct |
| Jobs are rejected | Check your resource group / billing group setting (you can specify it by saying "submit it under the XYZ group") |

## Next steps
- **Reverse-lookup catalog of what you can do (phrasing catalog)** → [docs/usage-catalog.en.md](docs/usage-catalog.en.md)
- **FAQ and troubleshooting** → [docs/faq.en.md](docs/faq.en.md)
- Detailed per-client configuration and other clients → [docs/clients.en.md](docs/clients.en.md)
- Multi-user operation and usage-history collection → [docs/multi-user.en.md](docs/multi-user.en.md)
- Safeguards (command restrictions, resource limits, auditing) → [docs/security.en.md](docs/security.en.md)
- Overall picture of how it works → [README](README.en.md)
