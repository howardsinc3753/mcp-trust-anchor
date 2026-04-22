---
name: trust-anchor-quickstart
description: Walk a user through cloning, installing, and testing the MCP Trust Anchor locally (Docker or native). Use when the user clones this repo and wants to get Trust Anchor running end-to-end with a first successful tool call.
---

# Trust Anchor Quickstart (Skill for Claude Code)

Use this skill when the user has just cloned the `mcp-trust-anchor` repo and
wants to stand it up on their workstation. Your job is to guide them from
`git clone` to a working signed-tool call in under 10 minutes, asking the minimum
number of questions and checking at each step that the previous step succeeded.

## Default assumptions (override only if user contradicts)

- They want the **Docker path** unless they say otherwise (fewest moving parts).
- They want to use whichever AI editor they currently have installed
  (Claude Desktop, Claude Code in VS Code, GitHub Copilot in VS Code).
- They don't have a real FortiGate on hand — use the mock.

## The flow

### 1. Detect state
Run, in parallel:
- `docker --version` (does Docker exist?)
- `python --version` / `python3 --version`
- Check for [README.md](../../README.md) to confirm we're in the right repo

Report back what you found in one sentence, then ask:

> "Docker available. I'd suggest the Docker path — one command, no Rocky VM needed. OK to go with that?"

If they'd rather do native, point to `server/install.sh` and defer to [QUICKSTART.md](../../QUICKSTART.md) Path B.

### 2. Start Trust Anchor
For Docker:
```bash
docker compose up -d
```
Then verify:
```bash
curl http://localhost:8000/health
```
Expected output contains `"status":"healthy"`. If not, read `docker compose logs trust-anchor` and diagnose.

### 3. Load sample tools (one-time)
```bash
python scripts/load-sample-tools.py --server http://localhost:8000
```
This re-signs every tool in `tools/` with the user's brand-new RSA key. Samples shipped in the repo are NOT pre-signed (or are signed under someone else's key) — this step is mandatory before the first tool call.

If they don't have Python locally, run via the container:
```bash
docker compose exec trust-anchor python /opt/trust-anchor/tools/register-tools.py --server http://localhost:8000 --tools-dir /opt/trust-anchor/tools
```

### 4. Wire up their editor
```bash
python scripts/configure-editors.py --server http://localhost:8000
```
This detects installed editors and writes the right MCP config for each. Remind them:
- Schema differs between Claude (`mcpServers`) and Copilot (`servers`) — the script handles this.
- **Restart the editor** after the script runs.
- For GitHub Copilot specifically, they must switch the chat-mode dropdown to **Agent**.

### 5. Stand up the mock target (only if no real FortiGate)
```bash
python scripts/mock-fortigate.py &
cp scripts/sample_credentials.yaml.example ~/.config/mcp/mock_credentials.yaml
```
(On Windows: `%USERPROFILE%\.config\mcp\mock_credentials.yaml`.)

### 6. First tool call (the payoff)
Instruct them to ask their editor:

> "List my accessible devices, then call fortigate-health-check against 127.0.0.1."

Expected result: they see the mock device listed, then a signed tool executes with signature verification passing, and a fake health response comes back. **This is the moment the stack is proven end-to-end.**

### 7. What next?
Offer three follow-ups:
- **Publish their own tool** — either via the CLI (`scripts/publish.py`) or conversationally ("publish path/to/my-tool.py"). The wizard's Skills.md walks through everything.
- **Swap in a real device** — edit `~/.config/mcp/mock_credentials.yaml` (or create `fortigate_credentials.yaml` per [client/bootstrap output](../../client/bootstrap.sh)) to point at their gear.
- **Read the architecture** — [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md).

## Things to watch out for

- **Port 8000 conflict.** If their workstation already has something on :8000, set `TRUST_ANCHOR_PORT=8001` in `.env` before `docker compose up`.
- **Signature errors.** 99% of the time this means they skipped step 3, or ran `load-sample-tools.py` against the wrong server, or regenerated keys after loading tools. Re-run step 3.
- **"No tools visible in Claude."** Restart the editor. Then check Claude Code output panel or Copilot agent logs for a stderr line like `Trust Anchor status: healthy`.
- **`PUBLISHER_KEYS=dev-publisher-key` is the default.** Fine for localhost, not fine for anything else. Flag this if they mention wanting to expose Trust Anchor beyond their workstation.

## Do NOT

- Do not try to configure a public tunnel (Cloudflare, ngrok) as part of this flow — that's only relevant if they're trying to integrate Microsoft Teams/M365 Copilot, which is out of scope here.
- Do not modify `server/install.sh`, `client/bootstrap.sh`, or `client/bootstrap.ps1` to "fix" issues. Those are the production paths; this skill is for local eval.
- Do not commit `.env`, `*_credentials.yaml`, or `*.pem` — they're in `.gitignore` for a reason.
