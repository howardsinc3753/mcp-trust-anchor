# FortiCloud IAM API User Create Skills

## Overview

This tool creates IAM API users in FortiCloud using **Playwright browser automation**. Fortinet does not provide an API for creating API users, so browser automation is required.

## When to Use

Use this tool when:
- You need to create API credentials for FortiCloud services
- Setting up automation for FortiFlex, Asset Management, or Organization APIs
- Provisioning API access for new MSSP integrations
- The AI needs its own API credentials for FortiCloud operations

**Example prompts:**
- "Create an API user for FortiFlex automation"
- "Set up API credentials for FortiCloud with Organization scope"
- "Create an IAM API user with read-write access to Asset Management"

## Prerequisites

1. **FortiCloud Portal Account** with Admin access to IAM
2. **Playwright installed**: `pip install playwright && playwright install chromium`
3. **Portal credentials** configured (username/password for web login)
4. **MFA secret** (if 2FA is enabled on the account)

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_name` | string | **Yes** | - | Display name for the API user |
| `permissions` | array | **Yes** | - | List of permission configurations |
| `description` | string | No | - | Optional description |
| `portal_username` | string | No | from config | Portal login email |
| `portal_password` | string | No | from config | Portal password |
| `mfa_secret` | string | No | - | TOTP secret for 2FA |
| `headless` | boolean | No | true | Run browser in headless mode |
| `save_credentials` | boolean | No | true | Save creds to config file |

### Permission Object Format

```json
{
  "portal": "FlexVM",
  "access": "Admin",
  "scope": "Organization"
}
```

**Available Portals:**
- `FlexVM` / `FortiFlex` - FortiFlex licensing
- `Asset Management` - Product registration
- `Organization` - OU management
- `IAM` - Identity management
- `FortiGate Cloud` - FortiGate cloud management
- `FortiAnalyzer Cloud` - FortiAnalyzer cloud
- `FortiSASE` - FortiSASE management

**Access Levels:**
- `Admin` - Full control
- `ReadWrite` - Read and modify
- `ReadOnly` - Read only

**Scopes:**
- `Local` - Own account only
- `Organization` - All OUs under the organization

## Example Usage

### Create Full-Access API User

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-iam-user-create/1.0.0",
    parameters={
        "user_name": "ulysses-automation",
        "description": "Ulysses MCP automation API user",
        "permissions": [
            {"portal": "FlexVM", "access": "Admin", "scope": "Organization"},
            {"portal": "Asset Management", "access": "ReadWrite", "scope": "Organization"},
            {"portal": "Organization", "access": "ReadWrite", "scope": "Organization"}
        ],
        "headless": True,
        "save_credentials": True
    }
)
```

### Create Read-Only API User

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-iam-user-create/1.0.0",
    parameters={
        "user_name": "ulysses-readonly",
        "permissions": [
            {"portal": "FlexVM", "access": "ReadOnly", "scope": "Organization"},
            {"portal": "Asset Management", "access": "ReadOnly", "scope": "Local"}
        ]
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "api_username": "217CD4CB-742D-439A-B907-460AF16D894C",
  "api_password": "6c383acce9c57066ff586ce846bd65f2!1Aa",
  "user_name": "ulysses-automation",
  "permissions": [
    {"portal": "FlexVM", "access": "Admin", "scope": "Organization"}
  ],
  "credentials_saved_to": "C:/ProgramData/Ulysses/config/forticloud_credentials.yaml"
}
```

### Important Notes

- **API password is shown ONLY ONCE** - The password cannot be retrieved again after creation
- If `save_credentials: true`, credentials are automatically saved to the config file
- Screenshots are saved to `screenshots/` for debugging

## Credential File Format

After successful creation, credentials are saved:

```yaml
# forticloud_credentials.yaml
api_username: "217CD4CB-742D-439A-B907-460AF16D894C"
api_password: "6c383acce9c57066ff586ce846bd65f2!1Aa"

api_users:
  ulysses-automation:
    api_username: "217CD4CB-742D-439A-B907-460AF16D894C"
    api_password: "6c383acce9c57066ff586ce846bd65f2!1Aa"
    permissions:
      - portal: FlexVM
        access: Admin
        scope: Organization
    created_at: "2026-01-16T10:30:00"
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Playwright not installed` | Missing dependency | Run install command |
| `Portal credentials required` | No login creds | Configure portal.username/password |
| `Failed to login` | Bad credentials or MFA | Check creds, provide mfa_secret |
| `Could not find Add API User button` | Page structure changed | Check screenshots, update tool |
| `Could not capture credentials` | UI timing issue | Check screenshots/iam_created_*.png |

## Debugging

Set `headless: false` to watch the browser automation:

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-iam-user-create/1.0.0",
    parameters={
        "user_name": "test-user",
        "permissions": [...],
        "headless": False  # Watch the browser
    }
)
```

Screenshots are saved to `screenshots/` directory:
- `login_failed.png` - If login fails
- `iam_debug.png` - If Add button not found
- `iam_created_{user_name}.png` - After creation

## Related Tools

- `forticloud-browser-base` - Base library for browser automation
- `forticloud-ou-list` - List OUs (uses API credentials from this tool)
- `fortiflex-token-create` - Create FortiFlex tokens (uses API credentials)

## API Credential Usage

After creating an API user, use the credentials with API-based tools:

```python
# The created credentials are automatically used by other FortiCloud tools
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-ou-list/1.0.0",
    parameters={}  # Uses credentials from config file
)
```

Or pass explicitly:

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-ou-list/1.0.0",
    parameters={
        "api_username": "217CD4CB-742D-439A-B907-460AF16D894C",
        "api_password": "6c383acce9c57066ff586ce846bd65f2!1Aa"
    }
)
```
