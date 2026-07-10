[日本語](QUICKSTART.md) | English

# Quickstart — Using Fugaku from Your AI Assistant

Just by talking to Claude Code, you can run jobs, manage files, and check status on Fugaku.
**Takes about 5 minutes.** No programming knowledge required.

## 0. What you need beforehand

- A **Fugaku account** and an **X.509 client certificate (a `.p12` file)** (issued via the HPCI/R-CCS portal)
- **Claude Code** (desktop app or CLI)
- **Python 3.10 or later**, plus `git` and `openssl` (standard on Mac/Linux; check with `python3 --version`)
- Network: **No VPN required** (the Fugaku WebAPI is publicly available on the internet and authenticates via certificate)

## 1. Installation (first time only)

```bash
# Get the tool and set up a dedicated Python environment
git clone https://github.com/RIKEN-RCCS/fugaku-mcp.git
cd fugaku-mcp
python3 -m venv .venv
.venv/bin/pip install "mcp[cli]"
```

> If installing `mcp` fails on Python 3.14, use 3.12 instead with `python3.12 -m venv .venv`.

## 2. Register your certificate (first time only)

Just hand over the `.p12` file you downloaded. Conversion, connectivity check, and configuration-file generation are all automated.

```bash
./setup_user.sh ~/Downloads/your-certificate.p12
```

- Partway through, you will be asked for the **certificate passphrase** (the one you set when the certificate was issued).
- On success, a **ready-to-paste `.mcp.json`** is displayed at the end.

## 3. Register with Claude Code (first time only)

1. Save the contents of the `.mcp.json` shown in step 2 as a file named `.mcp.json` **directly inside the folder (project) you use with Claude Code**.
2. **Fully restart Claude Code.**
   - Mac: bring the app to the front and press **⌘Q** (just closing the window with ✕ is not enough), then launch it again.
3. If you are prompted "Allow the MCP server `fugaku`?" on startup, choose **Allow**.

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
| The `fugaku` tools don't appear | **Quit completely with ⌘Q** and restart (closing with ✕ or closing the window doesn't take effect). Check that `.mcp.json` is in the folder |
| Authentication error / can't get status | Run `setup_user.sh` again to verify certificate connectivity. Also check whether the certificate has expired |
| "Certificate not found" | Check that the path in `FUGAKU_CERT` in `.mcp.json` is correct |
| Jobs are rejected | Check your resource group / billing group setting (you can specify it by saying "submit it under the XYZ group") |

## Next steps
- **Reverse-lookup catalog of what you can do (phrasing catalog)** → [docs/usage-catalog.en.md](docs/usage-catalog.en.md)
- **FAQ and troubleshooting** → [docs/faq.en.md](docs/faq.en.md)
- Multi-user operation and usage-history collection → [docs/multi-user.en.md](docs/multi-user.en.md)
- Safeguards (command restrictions, resource limits, auditing) → [docs/security.en.md](docs/security.en.md)
- Overall picture of how it works → [README](README.en.md)
