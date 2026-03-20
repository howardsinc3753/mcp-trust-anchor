# FortiSASE Browser Automation Base Skills

## Overview

Browser automation foundation for FortiSASE portal operations. This tool provides the core login, navigation, and session management capabilities used by other FortiSASE tools when API access is not available.

## When to Use

Use this tool when:
- Testing FortiSASE portal login automation
- Navigating to specific FortiSASE sections
- Taking screenshots for documentation or troubleshooting
- Extracting table data from FortiSASE pages
- As a building block for more complex FortiSASE automation

**Example prompts:**
- "Login to FortiSASE and take a screenshot"
- "Navigate to the users section in FortiSASE"
- "Test FortiSASE portal access"

## Prerequisites

1. **Playwright Installed** - `pip install playwright && playwright install chromium`
2. **FortiSASE Credentials** - Portal username and password configured
3. **MFA Secret** (optional) - Base32 TOTP secret if MFA enabled

## Configuration

Add FortiSASE credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
fortisase:
  username: "your-email@company.com"
  password: "your-password"
  tenant_id: "your-tenant-id"       # Optional
  mfa_secret: "ABCD1234EFGH5678"    # Optional - base32 TOTP secret
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | No | "login" | Action to perform |
| `section` | string | No | - | Portal section for navigate |
| `screenshot_name` | string | No | "fortisase" | Screenshot filename prefix |
| `headless` | boolean | No | true | Run browser headless |
| `username` | string | No | from config | Override portal username |
| `password` | string | No | from config | Override portal password |
| `tenant_id` | string | No | from config | Tenant/org ID |
| `mfa_secret` | string | No | from config | TOTP secret for MFA |

## Available Actions

| Action | Description |
|--------|-------------|
| `login` | Authenticate to FortiSASE portal |
| `navigate` | Login + navigate to section |
| `screenshot` | Take screenshot of current page |
| `get_data` | Extract table data from page |

## Portal Sections

| Section | Path | Description |
|---------|------|-------------|
| `dashboard` | /dashboard | Main dashboard |
| `users` | /users | User management |
| `endpoints` | /endpoints | Endpoint management |
| `policies` | /policies | Policy configuration |
| `security-policies` | /security-policies | Security rules |
| `web-filter` | /web-filter | Web filtering |
| `dns-filter` | /dns-filter | DNS filtering |
| `ssl-inspection` | /ssl-inspection | SSL inspection |
| `logs` | /logs | Log viewer |
| `reports` | /reports | Reports |
| `settings` | /settings | Settings |
| `admin` | /admin | Administration |

## Example Usage

### Login Test

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortisase-browser-base/1.0.0",
    parameters={
        "action": "login"
    }
)
```

### Navigate to Users Section

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortisase-browser-base/1.0.0",
    parameters={
        "action": "navigate",
        "section": "users"
    }
)
```

### Take Screenshot

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortisase-browser-base/1.0.0",
    parameters={
        "action": "screenshot",
        "screenshot_name": "fortisase_dashboard"
    }
)
```

### Non-Headless (Visible Browser)

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortisase-browser-base/1.0.0",
    parameters={
        "action": "login",
        "headless": false
    }
)
```

## Interpreting Results

### Successful Login

```json
{
  "success": true,
  "action": "login",
  "message": "Login successful",
  "current_url": "https://www.fortisase.com/dashboard"
}
```

### Screenshot Result

```json
{
  "success": true,
  "action": "screenshot",
  "path": "C:/ProgramData/Ulysses/sessions/fortisase_20260116_143022.png"
}
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Playwright not installed` | Missing dependency | Run: pip install playwright && playwright install chromium |
| `Credentials not configured` | No username/password | Add to credentials file |
| `Login failed` | Invalid credentials | Verify username/password |
| `MFA required` | Need TOTP code | Configure mfa_secret |
| `Timeout` | Page load too slow | Increase timeout or check network |

## MFA Configuration

If your FortiSASE account has MFA enabled:

1. Get your TOTP secret from FortiCloud account settings
2. The secret is usually shown as a QR code - get the text version
3. Add to credentials file as `mfa_secret`

The tool will automatically generate and enter TOTP codes during login.

## Related Tools

- `fortisase-user-list` - List FortiSASE users
- `fortisase-user-create` - Create FortiSASE users
- `forticloud-browser-base` - FortiCloud portal automation
- `forticloud-iam-user-create` - IAM user creation

## Notes

- Screenshots are saved to `C:\ProgramData\Ulysses\sessions\`
- Browser runs headless by default (set `headless: false` to see browser)
- Session timeout is 3 minutes (180000ms)
- Uses Chromium browser via Playwright
