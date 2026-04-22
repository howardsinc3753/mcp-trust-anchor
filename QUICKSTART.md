# Quickstart — MCP Trust Anchor in 3 minutes

The shortest path from `git clone` to Claude (or GitHub Copilot) calling a
signed tool against your own Trust Anchor. Two deployment choices — pick one.

---

## Path A — Docker (easiest, recommended for local eval)

Works on macOS, Windows, Linux. Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/)
or Docker Engine + Compose v2.

```bash
git clone <repo-url> mcp-trust-anchor
cd mcp-trust-anchor

# Start Trust Anchor + Redis (keys auto-generated on first run)
docker compose up -d

# Verify it's up
curl http://localhost:8000/health
# → {"status":"healthy"}
```

That's the server. Jump to **Step 3 — Load sample tools** below.

---

## Path B — Native install (Rocky Linux / RHEL)

Production deployment or if you specifically want a systemd service.

```bash
git clone <repo-url> mcp-trust-anchor
cd mcp-trust-anchor
sudo ./server/install.sh
curl http://localhost:8000/health
```

---

## Step 3 — Load the sample tools

The tools in `tools/` are unsigned until your Trust Anchor signs them. This
one-time step re-signs all samples under your brand-new RSA key:

```bash
python scripts/load-sample-tools.py --server http://localhost:8000
```

If you don't have Python 3.10+ on your workstation, run it inside the container:

```bash
docker compose exec trust-anchor python /opt/trust-anchor/tools/register-tools.py \
    --server http://localhost:8000 \
    --tools-dir /opt/trust-anchor/tools
```

---

## Step 4 — Point your AI editor at it

You have three editors that speak MCP. The helper script below detects whichever
ones you have installed and writes the correct config for each — no manual JSON
editing. All three use the **same Trust Anchor**, and you can run them side-by-side.

```bash
python scripts/configure-editors.py --server http://localhost:8000
```

**What it writes:**

| Editor | Config file it touches |
|---|---|
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` (Windows) / `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) / `~/.config/Claude/claude_desktop_config.json` (Linux) |
| Claude Code (VS Code extension) | `%APPDATA%\Code\User\mcp.json` (Windows) / equivalent on Mac/Linux |
| GitHub Copilot (VS Code) | Same as above — Copilot uses `servers:` top-level key, Claude uses `mcpServers:` — the script handles the schema difference for you |

Restart the editor(s) after running. For Copilot, switch to **Agent** mode in chat.

---

## Step 5 — Prove it works

### No FortiGate on hand? Use the mock

The sample tools want to talk to a real FortiGate. If you just want to see the
signature-verification pipeline end-to-end, run the mock:

```bash
# Terminal 1 — start the mock FortiGate (responds on localhost:8443)
python scripts/mock-fortigate.py

# Copy the sample credential file so the MCP bridge can find the mock
cp scripts/sample_credentials.yaml.example ~/.config/mcp/mock_credentials.yaml
# On Windows: copy to %USERPROFILE%\.config\mcp\mock_credentials.yaml
```

Or enable the mock as a compose service:

```bash
docker compose --profile mock up -d
```

### Ask your editor to call a tool

Open Claude Code / Claude Desktop / GitHub Copilot Chat and try:

> *"List my accessible devices."*

You should see `mock-fortigate` at `127.0.0.1:8443`. Then:

> *"Call fortigate-health-check against 127.0.0.1."*

You should see a signed tool execute, the signature get verified against your
brand-new public key, and a fake-but-structurally-real health response come back.

---

## Step 6 (optional) — Publish your own tool

Write a Python file with a `main(context)` entry point, then:

```bash
python scripts/publish.py \
    path/to/my-tool.py \
    --domain noc \
    --intent monitor \
    --description "What my tool does"
```

…or let your AI editor do it for you:

> *"Publish `path/to/my-tool.py` as a new NOC monitoring tool."*

Claude Code (or any MCP-aware agent) will discover the publisher wizard tool,
read its Skills.md, and do the publish. See
[docs/TOOL-AUTHORING.md](docs/TOOL-AUTHORING.md) for the full manual-path guide.

---

## Troubleshooting

**`docker compose up` fails with "port already in use"**
Change `TRUST_ANCHOR_PORT` in a `.env` file — see [.env.example](.env.example).

**Signature verification error after `load-sample-tools.py`**
You ran `load-sample-tools.py` against the wrong server, or the server's keys
were rotated since tools were registered. Re-run the load script.

**Claude Code / Copilot doesn't see the tools**
1. Did you restart the editor after running `configure-editors.py`?
2. For Copilot: are you in **Agent** mode (not Ask / Edit)?
3. Run `docker compose logs -f trust-anchor` and look for "Trust Anchor status: healthy" on the client side.

**"Could not reach Trust Anchor"**
The MCP bridge on your workstation can't reach the URL it was configured with.
Check `curl http://<url>/health` from the workstation where the editor runs.

---

## What just happened?

1. Trust Anchor generated a fresh RSA-2048 keypair and came up on `:8000`.
2. `load-sample-tools.py` submitted each tool in `tools/` to the publisher API, which signed them with your private key and stored them in Redis.
3. `configure-editors.py` wrote MCP server configs pointing your editors at a local Python bridge (`client/mcp_bridge/MCP-secure-tools-server.py`).
4. When your editor calls a tool, the bridge fetches the code + signature from Trust Anchor, verifies the signature with your cached public key, and only then executes the tool locally. Credentials for target devices stay on your workstation — they never leave.

Deeper dives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/TOOL-AUTHORING.md](docs/TOOL-AUTHORING.md).
