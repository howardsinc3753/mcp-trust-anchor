#!/usr/bin/env python3
"""
configure-editors.py — write MCP server config for every supported AI editor
detected on this workstation.

This is the one-command way to wire Claude Desktop, Claude Code (VS Code extension),
and GitHub Copilot (VS Code) to your Trust Anchor. Each editor uses a slightly
different config file and JSON schema; this script handles all three.

It is NON-DESTRUCTIVE:
  - If a config file exists, we MERGE (preserving your other MCP servers).
  - If the "secure-tools" entry already exists, we update in place.
  - We never touch keys we didn't write.
  - Existing files get a `.bak` copy the first time we modify them.

Usage:
    python scripts/configure-editors.py [--server http://localhost:8000]
                                        [--bridge-python /path/to/python]
                                        [--bridge-script /path/to/MCP-secure-tools-server.py]
                                        [--only claude-desktop,claude-code,copilot]
                                        [--dry-run]

Defaults:
  --server        http://localhost:8000
  --bridge-python uses the python running this script (sys.executable)
  --bridge-script <repo>/client/mcp_bridge/MCP-secure-tools-server.py
"""

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Editor profiles
# ---------------------------------------------------------------------------

def _claude_desktop_path() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Claude" / "claude_desktop_config.json"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _vscode_user_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Code" / "User"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User"
    return Path.home() / ".config" / "Code" / "User"


def _claude_code_path() -> Path:
    # Claude Code (Anthropic VS Code extension) — uses mcpServers schema.
    # Stored under VS Code user dir as mcp.json (same file GitHub Copilot uses;
    # different top-level keys coexist because it's a merged config).
    return _vscode_user_dir() / "mcp.json"


def _copilot_path() -> Path:
    # GitHub Copilot (VS Code) — same mcp.json, `servers` schema.
    return _vscode_user_dir() / "mcp.json"


EDITOR_PROFILES = {
    "claude-desktop": {
        "label": "Claude Desktop",
        "path_fn": _claude_desktop_path,
        "schema_key": "mcpServers",
    },
    "claude-code": {
        "label": "Claude Code (VS Code extension)",
        "path_fn": _claude_code_path,
        "schema_key": "mcpServers",
    },
    "copilot": {
        "label": "GitHub Copilot (VS Code)",
        "path_fn": _copilot_path,
        "schema_key": "servers",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent


def build_server_block(bridge_python: Path, bridge_script: Path, trust_anchor_url: str, credential_path: Path) -> dict:
    return {
        "command": str(bridge_python),
        "args": [str(bridge_script)],
        "env": {
            "TRUST_ANCHOR_URL": trust_anchor_url,
            "CREDENTIAL_PATH": str(credential_path),
        },
    }


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  ! existing file at {path} is not valid JSON ({e}); skipping to avoid damage")
        return None


def backup_once(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    if path.exists() and not bak.exists():
        shutil.copy2(path, bak)
        print(f"  backed up existing file to {bak.name}")


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_config(profile_key: str, profile: dict, server_block: dict, dry_run: bool) -> str:
    path = profile["path_fn"]()
    schema_key = profile["schema_key"]

    existing = load_json(path)
    if existing is None:
        return "skipped (invalid existing JSON)"
    merged = dict(existing)
    merged.setdefault(schema_key, {})
    previously_present = "secure-tools" in merged[schema_key]
    merged[schema_key]["secure-tools"] = server_block

    if dry_run:
        return f"DRY-RUN would write {path} (schema key '{schema_key}', secure-tools {'updated' if previously_present else 'added'})"

    backup_once(path)
    write_json_atomic(path, merged)
    return f"wrote {path} (secure-tools {'updated' if previously_present else 'added'})"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    repo_root = detect_repo_root()
    default_bridge_script = repo_root / "client" / "mcp_bridge" / "MCP-secure-tools-server.py"

    p = argparse.ArgumentParser(description="Write MCP config for detected AI editors.")
    p.add_argument("--server", default=os.environ.get("TRUST_ANCHOR_URL", "http://localhost:8000"))
    p.add_argument("--bridge-python", default=sys.executable, type=Path)
    p.add_argument("--bridge-script", default=default_bridge_script, type=Path)
    p.add_argument(
        "--credential-path",
        default=Path.home() / ".config" / "mcp",
        type=Path,
        help="Directory the MCP bridge scans for *_credentials.yaml",
    )
    p.add_argument(
        "--only",
        default=",".join(EDITOR_PROFILES.keys()),
        help=f"Comma-separated editor keys. Choices: {', '.join(EDITOR_PROFILES.keys())}",
    )
    p.add_argument("--dry-run", action="store_true", help="Print what would change without writing anything")
    args = p.parse_args()

    if not args.bridge_script.exists():
        print(f"! bridge script not found at {args.bridge_script}")
        print("  Either run ./client/bootstrap.sh (or bootstrap.ps1) first to install it,")
        print("  or pass --bridge-script pointing at your bridge.")
        sys.exit(1)

    targets = [t.strip() for t in args.only.split(",") if t.strip()]
    unknown = [t for t in targets if t not in EDITOR_PROFILES]
    if unknown:
        sys.exit(f"error: unknown editor(s): {unknown}. Valid: {list(EDITOR_PROFILES)}")

    args.credential_path.mkdir(parents=True, exist_ok=True)
    server_block = build_server_block(args.bridge_python, args.bridge_script, args.server, args.credential_path)

    print(f"Trust Anchor:   {args.server}")
    print(f"Bridge python:  {args.bridge_python}")
    print(f"Bridge script:  {args.bridge_script}")
    print(f"Credentials:    {args.credential_path}")
    print(f"Targets:        {targets}")
    print()

    results = {}
    for key in targets:
        profile = EDITOR_PROFILES[key]
        path = profile["path_fn"]()
        present = path.exists()
        print(f"[{profile['label']}]")
        print(f"  config file: {path} ({'exists' if present else 'will create'})")
        try:
            msg = write_config(key, profile, server_block, args.dry_run)
        except Exception as e:
            msg = f"FAILED: {e}"
        print(f"  -> {msg}")
        results[key] = msg
        print()

    print("Done.")
    print("Next:")
    print("  1. Restart the editor(s) you configured.")
    print("  2. In GitHub Copilot Chat, switch the mode dropdown to 'Agent'.")
    print("  3. Try: 'list my accessible devices'.")


if __name__ == "__main__":
    main()
