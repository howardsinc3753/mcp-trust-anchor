# FortiSASE User Create Skills

## Overview

Create users in FortiSASE via browser automation. Since FortiSASE does not provide a public API for user management, this tool uses Playwright to automate the user creation workflow in the FortiSASE portal.

## When to Use

Use this tool when:
- Onboarding new users to FortiSASE
- Automating user provisioning as part of employee onboarding
- Creating multiple users programmatically
- Setting up users with specific group assignments

**Example prompts:**
- "Create a new FortiSASE user for john.doe@company.com"
- "Add user Jane Smith to FortiSASE with email jane.smith@company.com"
- "Onboard new employee to FortiSASE"

## Prerequisites

1. **Playwright Installed** - `pip install playwright && playwright install chromium`
2. **FortiSASE Admin Account** - Portal admin with user management permissions
3. **MFA Secret** (optional) - Base32 TOTP secret if admin account has MFA

## Configuration

Add FortiSASE admin credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
fortisase:
  username: "admin@company.com"
  password: "admin-password"
  tenant_id: "your-tenant-id"
  mfa_secret: "ABCD1234EFGH5678"  # Optional - base32 TOTP secret
```

**Important**: The `fortisase:` section is empty by default. You must configure these credentials before using FortiSASE tools.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `email` | string | **Yes** | - | User email address |
| `first_name` | string | No | - | User first name |
| `last_name` | string | No | - | User last name |
| `user_group` | string | No | - | Group to assign user to |
| `send_invite` | boolean | No | true | Send invitation email |
| `headless` | boolean | No | true | Run browser headless |
| `admin_username` | string | No | from config | Override admin username |
| `admin_password` | string | No | from config | Override admin password |
| `mfa_secret` | string | No | from config | Admin TOTP secret |

## Example Usage

### Create Basic User

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortisase-user-create/1.0.0",
    parameters={
        "email": "john.doe@company.com"
    }
)
```

### Create User with Full Details

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortisase-user-create/1.0.0",
    parameters={
        "email": "jane.smith@company.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "user_group": "Engineering",
        "send_invite": true
    }
)
```

### Create User Without Invite

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.fortisase-user-create/1.0.0",
    parameters={
        "email": "test.user@company.com",
        "first_name": "Test",
        "last_name": "User",
        "send_invite": false
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "message": "User john.doe@company.com created successfully",
  "user": {
    "email": "john.doe@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "user_group": "Engineering",
    "invite_sent": true
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": "User with this email already exists"
}
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Missing email` | No email provided | Provide email parameter |
| `Invalid email format` | Malformed email | Check email format |
| `Admin credentials not configured` | Missing login | Configure fortisase section |
| `Failed to login` | Auth failed | Verify admin credentials |
| `User already exists` | Duplicate email | Use different email |
| `Permission denied` | Admin lacks permissions | Use admin with user management rights |

## Input Validation

The tool validates inputs before submission:
- **Email**: Must be valid email format
- **Names**: Only alphanumeric, spaces, hyphens, underscores, periods

## Workflow Steps

1. Launch headless Chromium browser
2. Navigate to FortiCloud login
3. Authenticate with admin credentials
4. Handle MFA if configured
5. Navigate to Users section
6. Click Add User button
7. Fill in user details form
8. Submit and verify success
9. Return result

## Related Tools

- `fortisase-browser-base` - Base browser automation
- `fortisase-user-list` - List existing users
- `forticloud-iam-user-create` - Create IAM API users

## Notes

- Browser automation may take 30-60 seconds
- Run with `headless: false` to watch the browser
- Invitation emails are sent by FortiSASE, not this tool
- Timeout is 3 minutes per operation
