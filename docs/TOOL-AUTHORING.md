# Tool Authoring Guide

This guide explains how to create, sign, and deploy tools for the MCP Trust Anchor framework.

## Overview

A tool consists of three files:

```
my-tool/
├── manifest.yaml      # Tool metadata and parameters
├── my_tool.py         # Python implementation
└── Skills.md          # AI guidance document
```

## Quick Start

### 1. Create Tool Directory

```bash
mkdir tools/my-new-tool
cd tools/my-new-tool
```

### 2. Create manifest.yaml

```yaml
canonical_id: "org.example.my-new-tool/1.0.0"
name: "My New Tool"
version: "1.0.0"
description: "Description of what this tool does"

metadata:
  domain: "noc"           # noc, security, workstation, etc.
  vendor: "example"       # Vendor name
  author: "Your Name"
  intent: "troubleshoot"  # troubleshoot, monitor, configure, etc.
  tags:
    - example
    - demo

runtime:
  language: "python"
  min_version: "3.10"

parameters:
  - name: "target"
    type: "string"
    required: true
    description: "Target to operate on"
  - name: "option"
    type: "boolean"
    required: false
    default: false
    description: "Optional flag"

capabilities:
  network_access: true
  file_access: false
  requires_credentials: true

skills_ref: "Skills.md"
```

### 3. Create Python Implementation

```python
"""
My New Tool

Brief description of what this tool does.
"""

def main(context):
    """
    Main entry point for tool execution.

    Args:
        context: ExecutionContext with:
            - parameters: Dict of input parameters
            - credentials: Dict of credentials (if any)
            - metadata: Tool manifest and execution info

    Returns:
        dict: Result with 'success' boolean and data
    """
    # Get parameters
    params = context.parameters
    target = params.get("target")
    option = params.get("option", False)

    # Validate required parameters
    if not target:
        return {
            "success": False,
            "error": "target is required"
        }

    # Get credentials if needed
    creds = getattr(context, "credentials", {})
    api_key = creds.get("api_key")

    try:
        # Your tool logic here
        result = do_something(target, option, api_key)

        return {
            "success": True,
            "result": result,
            "target": target
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "target": target
        }
```

### 4. Create Skills.md

```markdown
# My New Tool Skills

## When to Use

Use this tool when:
- User asks about [specific task]
- User mentions [keywords]
- Troubleshooting [scenario]

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target | string | Yes | Target to operate on |
| option | boolean | No | Enable optional feature |

## Example Usage

**User:** "Check the status of server1"

**Tool Call:**
```python
my_new_tool(target="server1")
```

## Interpreting Results

- `success: true` means operation completed
- Check `result` field for actual data
- `error` field contains failure reason

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| target is required | Missing parameter | Ask user for target |
| Connection failed | Network issue | Check connectivity |
```

### 5. Register the Tool

```bash
# Submit to Trust Anchor
python tools/register-tools.py --server http://localhost:8000
```

## Manifest Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `canonical_id` | string | Unique identifier (format: `org.vendor.tool-name/version`) |
| `name` | string | Human-readable name |
| `version` | string | Semantic version (e.g., `1.0.0`) |
| `description` | string | Brief description |

### Metadata Section

```yaml
metadata:
  domain: "noc"           # Tool domain
  vendor: "fortinet"      # Vendor/manufacturer
  author: "Your Name"     # Tool author
  intent: "troubleshoot"  # Primary use case
  tags:                   # Searchable tags
    - network
    - monitoring
```

**Domains:** `noc`, `security`, `workstation`, `docs`, `demo`

**Intents:** `troubleshoot`, `monitor`, `configure`, `report`, `test`

### Parameters Section

```yaml
parameters:
  - name: "param_name"
    type: "string"        # string, integer, boolean, number
    required: true
    default: "value"      # Optional default
    description: "Help text"
    format: "ipv4"        # Optional format hint
```

**Supported types:**
- `string` - Text values
- `integer` - Whole numbers
- `number` - Floating point
- `boolean` - true/false

### Capabilities Section

```yaml
capabilities:
  network_access: true    # Needs outbound network
  file_access: false      # Needs filesystem access
  requires_credentials: true  # Needs credentials
```

### Credentials Section

```yaml
credentials:
  - ref: "local://config/my_credentials.yaml"
    type: "config_file"
    required: false
    description: "Local credential file"
```

## Python Implementation

### Context Object

The `main()` function receives a context object with:

```python
context.parameters   # Dict of input parameters
context.credentials  # Dict of credentials (may be empty)
context.metadata     # Dict with manifest and execution info
```

### Return Format

Always return a dictionary with:

```python
# Success
return {
    "success": True,
    "result": {...},     # Your data
    "target": "..."      # Echo back target if applicable
}

# Failure
return {
    "success": False,
    "error": "Error message",
    "target": "..."
}
```

### Best Practices

1. **Validate inputs early**
   ```python
   if not params.get("target"):
       return {"success": False, "error": "target is required"}
   ```

2. **Handle credentials gracefully**
   ```python
   creds = getattr(context, "credentials", {})
   if not creds.get("api_key"):
       return {"success": False, "error": "No credentials configured"}
   ```

3. **Catch exceptions**
   ```python
   try:
       result = risky_operation()
   except SpecificError as e:
       return {"success": False, "error": f"Operation failed: {e}"}
   ```

4. **Use stdlib when possible**
   - Prefer `urllib.request` over `requests`
   - Minimize external dependencies

5. **Never log credentials**
   ```python
   # BAD
   logger.info(f"Connecting with token: {api_token}")

   # GOOD
   logger.info("Connecting to device")
   ```

## Skills.md Best Practices

The Skills.md file guides the AI on when and how to use your tool.

### Structure

1. **When to Use** - Trigger conditions
2. **Parameters** - Quick reference table
3. **Example Usage** - Concrete examples
4. **Interpreting Results** - How to explain output
5. **Error Handling** - Common errors and fixes

### Writing Tips

- Use clear, action-oriented language
- Include both "good" and "bad" use cases
- Provide realistic example prompts
- Explain result interpretation for the AI

## Tool Signing

Tools must be signed before execution. The signing process:

1. **Submit tool** to Trust Anchor
2. **Trust Anchor hashes** the code (SHA-256)
3. **Creates signing payload** with metadata + hash
4. **Signs payload** with RSA private key
5. **Stores signature** alongside tool

### Submit and Sign

```bash
# Using register-tools.py (recommended)
python tools/register-tools.py --server http://server:8000

# Or manually via API
curl -X POST http://server:8000/publisher/submit-tool \
  -H "X-Publisher-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"manifest": {...}, "code_python": "...", "skills_md": "..."}'

curl -X POST http://server:8000/publisher/certify/org.example.tool/1.0.0 \
  -H "X-Publisher-Key: your-key"
```

### Verification

When a client executes a tool:
1. Fetches tool + signature from Trust Anchor
2. Verifies signature with public key
3. Verifies code hash matches
4. Only executes if both pass

## Testing

### Local Testing

```python
# test_my_tool.py
from my_tool import main

class MockContext:
    def __init__(self, params, creds=None):
        self.parameters = params
        self.credentials = creds or {}
        self.metadata = {}

# Test basic execution
ctx = MockContext({"target": "test-target"})
result = main(ctx)
assert result["success"] == True

# Test missing parameter
ctx = MockContext({})
result = main(ctx)
assert result["success"] == False
assert "required" in result["error"]
```

### Integration Testing

```bash
# Register tool
python tools/register-tools.py --server http://localhost:8000

# Execute via API
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "canonical_id": "org.example.my-tool/1.0.0",
    "parameters": {"target": "test"}
  }'
```

## Versioning

### Version Bumping

When updating a tool:
1. Increment version in manifest (`1.0.0` → `1.0.1`)
2. Update `canonical_id` with new version
3. Re-submit and re-sign

### Breaking Changes

For breaking changes:
- Bump major version (`1.0.0` → `2.0.0`)
- Document changes in Skills.md
- Consider keeping old version available

## Example: Complete Tool

### manifest.yaml

```yaml
canonical_id: "org.example.ping-check/1.0.0"
name: "Ping Check"
version: "1.0.0"
description: "Check if a host is reachable via ping"

metadata:
  domain: "noc"
  vendor: "example"
  author: "NOC Team"
  intent: "troubleshoot"
  tags:
    - network
    - ping
    - connectivity

runtime:
  language: "python"
  min_version: "3.10"

parameters:
  - name: "host"
    type: "string"
    required: true
    description: "Host to ping"
  - name: "count"
    type: "integer"
    required: false
    default: 3
    description: "Number of ping attempts"

capabilities:
  network_access: true
  file_access: false
  requires_credentials: false

skills_ref: "Skills.md"
```

### ping_check.py

```python
"""
Ping Check Tool
Check if a host is reachable via ping.
"""

import subprocess
import platform


def main(context):
    params = context.parameters
    host = params.get("host")
    count = params.get("count", 3)

    if not host:
        return {"success": False, "error": "host is required"}

    # Build ping command (platform-specific)
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), host]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "success": result.returncode == 0,
            "host": host,
            "reachable": result.returncode == 0,
            "output": result.stdout,
            "ping_count": count
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Ping timed out",
            "host": host
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "host": host
        }
```

### Skills.md

```markdown
# Ping Check Skills

## When to Use

Use this tool when:
- User asks if a host is reachable
- User mentions "ping" or "connectivity"
- Troubleshooting network connectivity

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| host | string | Yes | Host to ping |
| count | integer | No | Ping count (default: 3) |

## Example

**User:** "Can you ping 192.168.1.1?"

**Tool Call:**
```python
ping_check(host="192.168.1.1")
```

**Response:**
```json
{
  "success": true,
  "reachable": true,
  "host": "192.168.1.1",
  "ping_count": 3
}
```

## Interpreting Results

- `reachable: true` - Host responded to ping
- `reachable: false` - Host did not respond
- Check `output` for detailed ping statistics

## Error Handling

| Error | Meaning |
|-------|---------|
| Ping timed out | Host unreachable or blocked |
| host is required | Missing host parameter |
```
