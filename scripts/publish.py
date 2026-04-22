#!/usr/bin/env python3
"""
publish.py — CLI wrapper around the Trust Anchor publisher wizard.

For users (or CI pipelines) that want to publish a tool without going through
an AI agent. The AI-driven path is still supported and preferred for humans:
in Claude Code or any MCP-aware agent, just say
"publish path/to/my-tool.py as a NOC monitoring tool" — the agent will discover
the wizard via Trust Anchor and drive it for you.

This script submits directly to the Trust Anchor publisher REST API:
    POST /publisher/submit-tool
    POST /publisher/certify/{canonical_id}

Usage:
    python scripts/publish.py PYTHON_FILE \\
        --domain noc \\
        --intent monitor \\
        --description "What the tool does" \\
        [--tool-name my-tool] \\
        [--vendor fortinet] \\
        [--version 1.0.0] \\
        [--server http://localhost:8000] \\
        [--publisher-key dev-publisher-key] \\
        [--dry-run]

The file must contain a `main(context)` function — see docs/TOOL-AUTHORING.md.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


VALID_DOMAINS = {
    "noc", "firewall", "soc", "ir", "threat-intel", "vuln-mgmt", "ids-ips",
    "edr", "workstation", "server", "iam", "cloud", "aws", "azure", "gcp",
    "kubernetes", "database", "docs", "sop", "hunt", "teach", "forge",
    "hive", "platform",
}

VALID_INTENTS = {
    "troubleshoot", "monitor", "provision", "remediate", "audit",
    "documentation", "discover", "execute", "configure", "analyze", "report",
}


def infer_tool_name(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"[_\s]+", "-", stem).lower()
    stem = re.sub(r"[^a-z0-9-]", "", stem)
    return stem or "unnamed-tool"


def load_code(path: Path) -> str:
    if not path.exists():
        sys.exit(f"error: file not found: {path}")
    if path.suffix != ".py":
        sys.exit(f"error: expected a .py file, got: {path.suffix}")
    code = path.read_text(encoding="utf-8")
    if "def main(" not in code:
        sys.exit(
            f"error: {path} has no `main(context)` function. "
            f"See docs/TOOL-AUTHORING.md for the required signature."
        )
    return code


def post_json(url: str, payload: dict, headers: dict, timeout: int = 30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


def main():
    p = argparse.ArgumentParser(description="Publish a Python tool to Trust Anchor")
    p.add_argument("python_file", type=Path, help="Path to the .py file containing your tool (must have main(context))")
    p.add_argument("--domain", required=True, help=f"Tool domain. One of: {', '.join(sorted(VALID_DOMAINS))}")
    p.add_argument("--intent", required=True, help=f"Tool intent. One of: {', '.join(sorted(VALID_INTENTS))}")
    p.add_argument("--description", required=True, help="Short human-readable description")
    p.add_argument("--tool-name", help="Tool name (lowercase, hyphenated). Inferred from filename if omitted.")
    p.add_argument("--vendor", default="generic")
    p.add_argument("--version", default="1.0.0")
    p.add_argument("--shelf", help="Shelf path (defaults to {domain}/custom)")
    p.add_argument("--server", default="http://localhost:8000", help="Trust Anchor base URL")
    p.add_argument("--publisher-key", default="dev-publisher-key", help="API key from PUBLISHER_KEYS")
    p.add_argument("--dry-run", action="store_true", help="Validate locally without hitting Trust Anchor")
    args = p.parse_args()

    if args.domain not in VALID_DOMAINS:
        sys.exit(f"error: invalid domain '{args.domain}'. Valid: {sorted(VALID_DOMAINS)}")
    if args.intent not in VALID_INTENTS:
        sys.exit(f"error: invalid intent '{args.intent}'. Valid: {sorted(VALID_INTENTS)}")

    tool_name = args.tool_name or infer_tool_name(args.python_file)
    shelf = args.shelf or f"{args.domain}/custom"
    canonical_id = f"org.local.{args.domain}.{tool_name}/{args.version}"

    code = load_code(args.python_file)
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()

    manifest = {
        "canonical_id": canonical_id,
        "name": tool_name,
        "version": args.version,
        "domain": args.domain,
        "intent": args.intent,
        "vendor": args.vendor,
        "shelf": shelf,
        "description": args.description,
        "code_hash": code_hash,
    }

    print(f"Tool:         {canonical_id}")
    print(f"Domain:       {args.domain} / intent: {args.intent} / vendor: {args.vendor}")
    print(f"Shelf:        {shelf}")
    print(f"Source:       {args.python_file} ({len(code)} bytes, sha256={code_hash[:12]}…)")
    print(f"Server:       {args.server}")

    if args.dry_run:
        print("\n[dry-run] Manifest that would be submitted:")
        print(json.dumps(manifest, indent=2))
        print("\n[dry-run] Not contacting Trust Anchor. Re-run without --dry-run to publish.")
        return

    headers = {"X-Publisher-Key": args.publisher_key}

    print("\nSubmitting to publisher…")
    status, body = post_json(
        f"{args.server.rstrip('/')}/publisher/submit-tool",
        {"manifest": manifest, "code": code, "skills": f"# {tool_name}\n\n{args.description}\n"},
        headers,
    )
    if status >= 300:
        sys.exit(f"error: submit failed ({status}): {body}")
    print(f"  submitted ({status}): {body.get('message', body) if isinstance(body, dict) else body}")

    print("\nCertifying (signing)…")
    status, body = post_json(
        f"{args.server.rstrip('/')}/publisher/certify/{canonical_id}",
        {},
        headers,
    )
    if status >= 300:
        sys.exit(f"error: certify failed ({status}): {body}")
    print(f"  certified ({status}): {body.get('message', body) if isinstance(body, dict) else body}")

    print(f"\nDone. Call it from your AI editor by canonical_id:")
    print(f"  {canonical_id}")


if __name__ == "__main__":
    main()
