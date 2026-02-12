#!/usr/bin/env python3
"""
Load Sample Tools into Trust Anchor

This is a wrapper around tools/register-tools.py that:
1. Finds the tools directory
2. Registers all sample tools
3. Verifies they're properly signed

Usage:
    python load-sample-tools.py [--server URL]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Load sample tools into Trust Anchor")
    parser.add_argument(
        "--server", "-s",
        default="http://localhost:8000",
        help="Trust Anchor server URL"
    )
    parser.add_argument(
        "--publisher-key", "-k",
        default="dev-publisher-key",
        help="Publisher API key"
    )
    args = parser.parse_args()

    # Find tools directory (relative to this script)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    tools_dir = repo_root / "tools"
    register_script = tools_dir / "register-tools.py"

    if not tools_dir.exists():
        print(f"Error: Tools directory not found: {tools_dir}")
        sys.exit(1)

    if not register_script.exists():
        print(f"Error: Register script not found: {register_script}")
        sys.exit(1)

    print("Loading sample tools into Trust Anchor...")
    print(f"  Server: {args.server}")
    print(f"  Tools: {tools_dir}")
    print()

    # Run the register script
    cmd = [
        sys.executable,
        str(register_script),
        "--server", args.server,
        "--publisher-key", args.publisher_key,
        "--tools-dir", str(tools_dir),
    ]

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
