#!/usr/bin/env python3
"""
Register Sample Tools with Trust Anchor

This script registers the sample tools with the Trust Anchor server.
Run after the server is installed and running.

Usage:
    python register-tools.py [--server URL]
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Error: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)


def load_tool(tool_dir: Path) -> dict:
    """Load tool files from a directory."""
    manifest_path = tool_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.yaml in {tool_dir}")

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Find Python code file
    code_python = None
    for py_file in tool_dir.glob("*.py"):
        if py_file.name != "__init__.py":
            with open(py_file) as f:
                code_python = f.read()
            break

    # Load Skills.md
    skills_md = None
    skills_path = tool_dir / "Skills.md"
    if skills_path.exists():
        with open(skills_path) as f:
            skills_md = f.read()

    return {
        "manifest": manifest,
        "code_python": code_python,
        "skills_md": skills_md,
    }


def submit_tool(client: httpx.Client, server_url: str, tool_data: dict, publisher_key: str) -> dict:
    """Submit a tool to Trust Anchor via Publisher API."""
    headers = {
        "X-Publisher-Key": publisher_key,
        "Content-Type": "application/json",
    }

    payload = {
        "manifest": tool_data["manifest"],
        "code_python": tool_data["code_python"],
        "skills_md": tool_data["skills_md"],
    }

    response = client.post(
        f"{server_url}/publisher/submit-tool",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def certify_tool(client: httpx.Client, server_url: str, canonical_id: str, publisher_key: str) -> dict:
    """Certify a tool (sign it)."""
    headers = {
        "X-Publisher-Key": publisher_key,
    }

    response = client.post(
        f"{server_url}/publisher/certify/{canonical_id}",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Register sample tools with Trust Anchor")
    parser.add_argument(
        "--server", "-s",
        default="http://localhost:8000",
        help="Trust Anchor server URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--publisher-key", "-k",
        default=os.environ.get("PUBLISHER_KEY", "dev-publisher-key"),
        help="Publisher API key (default: dev-publisher-key or PUBLISHER_KEY env var)"
    )
    parser.add_argument(
        "--tools-dir", "-t",
        default=None,
        help="Tools directory (default: same directory as this script)"
    )
    args = parser.parse_args()

    # Find tools directory
    if args.tools_dir:
        tools_dir = Path(args.tools_dir)
    else:
        tools_dir = Path(__file__).parent

    if not tools_dir.exists():
        print(f"Error: Tools directory not found: {tools_dir}")
        sys.exit(1)

    # Find all tool directories (those with manifest.yaml)
    tool_dirs = [d for d in tools_dir.iterdir() if d.is_dir() and (d / "manifest.yaml").exists()]

    if not tool_dirs:
        print(f"No tools found in {tools_dir}")
        sys.exit(1)

    print(f"Found {len(tool_dirs)} tools to register")
    print(f"Trust Anchor: {args.server}")
    print()

    # Create HTTP client
    client = httpx.Client(timeout=30.0, verify=False)

    # Check server is running
    try:
        response = client.get(f"{args.server}/health")
        if response.status_code != 200:
            print(f"Warning: Server health check returned {response.status_code}")
    except Exception as e:
        print(f"Error: Cannot connect to Trust Anchor at {args.server}")
        print(f"  {e}")
        sys.exit(1)

    # Register each tool
    for tool_dir in tool_dirs:
        print(f"Processing: {tool_dir.name}")

        try:
            # Load tool
            tool_data = load_tool(tool_dir)
            canonical_id = tool_data["manifest"].get("canonical_id", "unknown")
            print(f"  Canonical ID: {canonical_id}")

            # Submit tool
            print("  Submitting...")
            result = submit_tool(client, args.server, tool_data, args.publisher_key)
            print(f"  Submitted: {result.get('status', 'ok')}")

            # Certify tool (sign it)
            print("  Certifying (signing)...")
            cert_result = certify_tool(client, args.server, canonical_id, args.publisher_key)
            print(f"  Certified: {cert_result.get('status', 'ok')}")

            print(f"  SUCCESS: {canonical_id}")

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        print()

    print("Done!")


if __name__ == "__main__":
    main()
