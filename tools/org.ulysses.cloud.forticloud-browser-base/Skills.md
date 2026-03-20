# FortiCloud Browser Base Skills

## Overview

This is a **library tool** providing Playwright browser automation for FortiCloud portals. Use it as a foundation for building specialized browser-based tools.

## When to Use

Use browser automation when:
- The FortiCloud API doesn't support the operation
- You need to interact with FortiSASE portal
- You're creating IAM API users (UI-only workflow)
- You need to perform operations requiring human-like interaction

## How to Call

### Login to FortiCloud

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={
        "action": "login",
        "portal_username": "user@company.com",
        "portal_password": "password",
        "mfa_secret": "BASE32SECRETKEY",  # Optional TOTP secret
        "headless": True
    }
)
```

### Navigate to URL

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={
        "action": "navigate",
        "target_url": "https://support.fortinet.com/iam",
        "session_id": "session_20260116_123456"  # Reuse existing session
    }
)
```

### Take Screenshot

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={
        "action": "screenshot",
        "screenshot_path": "screenshots/debug.png",
        "session_id": "session_20260116_123456"
    }
)
```

### Logout / Close Browser

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={
        "action": "logout",
        "session_id": "session_20260116_123456"
    }
)
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | **Yes** | - | Action: login, navigate, screenshot, logout, get_session |
| `target_url` | string | For navigate | - | URL to navigate to |
| `portal_username` | string | For login | - | FortiCloud portal email |
| `portal_password` | string | For login | - | Portal password |
| `mfa_secret` | string | No | - | TOTP secret for 2FA (base32) |
| `headless` | boolean | No | true | Run browser in headless mode |
| `timeout_ms` | integer | No | 30000 | Page load timeout |
| `screenshot_path` | string | No | auto | Path for screenshot |
| `session_id` | string | No | auto | Session ID for reuse |

## Credential Sources

1. **Parameters**: `portal_username`, `portal_password`, `mfa_secret`
2. **Environment Variables**:
   - `FORTICLOUD_PORTAL_USERNAME`
   - `FORTICLOUD_PORTAL_PASSWORD`
   - `FORTICLOUD_MFA_SECRET`
3. **Config File** (`forticloud_credentials.yaml`):
   ```yaml
   portal:
     username: "user@company.com"
     password: "portal-password"
     mfa_secret: "BASE32SECRET"
   ```

## Session Management

Sessions allow you to:
- Reuse logged-in state across multiple tool calls
- Chain operations without re-authenticating
- Build complex workflows

### Example Workflow

```python
# Step 1: Login
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={"action": "login", "headless": False}
)
session_id = result["session_id"]

# Step 2: Navigate to IAM
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={
        "action": "navigate",
        "target_url": "https://support.fortinet.com/iam",
        "session_id": session_id
    }
)

# Step 3: Take screenshot for debugging
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={
        "action": "screenshot",
        "session_id": session_id
    }
)

# Step 4: Cleanup
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-browser-base/1.0.0",
    parameters={
        "action": "logout",
        "session_id": session_id
    }
)
```

## FortiCloud Portal URLs

| Portal | URL | Description |
|--------|-----|-------------|
| Main Login | `https://support.fortinet.com/login` | FortiCloud login |
| IAM Portal | `https://support.fortinet.com/iam` | Identity & Access Management |
| Asset Portal | `https://support.fortinet.com/asset` | Asset Management |
| FortiSASE | `https://portal.fortisase.com` | FortiSASE management |

## MFA / 2FA Handling

If your account has 2FA enabled:

1. Get your TOTP secret from your authenticator app setup
2. Encode it in base32 format
3. Pass as `mfa_secret` parameter

The tool will automatically:
- Detect MFA prompt
- Generate current TOTP code
- Submit the code

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Playwright not installed` | Missing dependency | Run: `pip install playwright && playwright install chromium` |
| `Browser not started` | start() not called | Internal error - report bug |
| `Login failed` | Invalid credentials | Check username/password |
| `MFA required but no secret` | 2FA enabled | Provide mfa_secret parameter |
| `Timeout` | Page didn't load | Increase timeout_ms |

## Building Specialized Tools

To create a tool that uses this base:

```python
from pathlib import Path
import sys

# Add tools directory to path
tools_dir = Path(__file__).parent.parent
sys.path.insert(0, str(tools_dir / "org.ulysses.cloud.forticloud-browser-base"))

from org_ulysses_cloud_forticloud_browser_base import FortiCloudBrowser, load_portal_credentials

async def my_specialized_tool(params):
    browser = FortiCloudBrowser(headless=True)
    await browser.start()

    # Login
    creds = load_portal_credentials(params)
    await browser.login(creds["portal_username"], creds["portal_password"])

    # Do specialized work
    await browser.navigate("https://support.fortinet.com/iam")
    # ... interact with page ...

    await browser.stop()
```

## Related Tools

- `forticloud-iam-user-create` - Create IAM API users (uses this base)
- `fortisase-tenant-create` - Create FortiSASE tenants (uses this base)
- `forticloud-ou-list` - List OUs (API-based, no browser needed)

## Prerequisites

```bash
# Install Playwright
pip install playwright pyotp

# Install browser
playwright install chromium
```
