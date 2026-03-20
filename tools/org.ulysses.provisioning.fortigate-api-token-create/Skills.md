# FortiGate API Token Create - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.provisioning.fortigate-api-token-create/1.0.0`
- **Domain:** provisioning
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Case
Initial FortiGate device onboarding when:
- Device has only admin/password configured
- No REST API admin exists yet
- Need to establish API access for automation

### Trigger Phrases
- "onboard new fortigate"
- "create api token for fortigate"
- "set up api access on fortigate"
- "provision fortigate api admin"
- "generate fortigate api key"

## Required Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| target_ip | string | Yes | FortiGate management IP |
| admin_password | string | Yes | Admin password (sensitive) |

## Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| admin_user | "admin" | Admin username |
| api_username | "ulysses-api" | Name for new API admin |
| accprofile | "super_admin" | Admin profile |
| trusthost | null | Allowed source IP/network |
| timeout | 30 | Request timeout (seconds) |
| verify_ssl | false | Verify SSL certificate |

## Example Usage

### Basic Onboarding
```json
{
  "target_ip": "192.168.215.15",
  "admin_password": "your-password-here"
}
```

### With Security Restrictions
```json
{
  "target_ip": "192.168.215.15",
  "admin_password": "your-password-here",
  "api_username": "automation-api",
  "accprofile": "prof_admin",
  "trusthost": "192.168.209.0/24"
}
```

## Output

### Success Response
```json
{
  "success": true,
  "target_ip": "192.168.215.15",
  "api_username": "ulysses-api",
  "api_token": "ABC123...",
  "accprofile": "super_admin",
  "message": "API admin 'ulysses-api' created successfully"
}
```

### Error Response
```json
{
  "success": false,
  "error": "API user 'ulysses-api' already exists",
  "suggestion": "Use a different api_username or delete existing user"
}
```

## Workflow Integration

This tool is typically Step 1 of device onboarding:

1. **fortigate-api-token-create** - Create API admin, get token
2. **fortigate-device-register** - Store token in credentials file
3. **fortigate-health-check** - Verify connectivity with new token

## Security Notes

- Admin password is passed at runtime, never stored
- Generated API token is sensitive - store securely
- Use `trusthost` to restrict API access by source IP
- Consider using `prof_admin` profile instead of `super_admin` for read-only use

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Login failed | Wrong admin/password | Verify credentials |
| User already exists | API admin name taken | Use different api_username |
| HTTP 403 | Admin lacks permission | Use super_admin account |
| Connection failed | Network/firewall issue | Check connectivity to FortiGate |

## Related Tools

- `fortigate-device-register` - Store credentials locally
- `fortigate-health-check` - Verify API connectivity
- `fortigate-ssh` - SSH-based CLI access
