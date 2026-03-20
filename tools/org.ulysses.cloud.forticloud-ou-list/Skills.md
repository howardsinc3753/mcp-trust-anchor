# FortiCloud OU List Skills

## How to Call

Use this tool when:
- User asks to list organizations or OUs in FortiCloud
- User needs to find Organization Unit IDs for customer management
- User wants to see the organizational hierarchy in FortiCloud
- User is setting up MSSP multi-tenant operations

**Example prompts:**
- "List all organizations in FortiCloud"
- "Show me the OU structure for my FortiCloud account"
- "What customers do I have in FortiCloud?"
- "Find OUs with 'Acme' in the name"

## Prerequisites

1. **FortiCloud IAM API User** with Organization scope
2. **Permissions**: Read access to Organization portal
3. **Client ID**: `organization`

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `parent_id` | integer | No | - | Filter by parent OU ID |
| `name_pattern` | string | No | - | Search pattern for OU name |
| `api_username` | string | No | - | Override credential file |
| `api_password` | string | No | - | Override credential file |

## Credential Sources (Priority Order)

1. **Parameters**: `api_username` and `api_password`
2. **Environment**: `FORTICLOUD_API_USERNAME` and `FORTICLOUD_API_PASSWORD`
3. **Config File**: `C:/ProgramData/Ulysses/config/forticloud_credentials.yaml`

### Credential File Format

```yaml
# C:\ProgramData\Ulysses\config\forticloud_credentials.yaml
# FortiCloud IAM API User credentials
api_username: "YOUR-API-USER-ID"
api_password: "your-api-password"

# Required for Org-scope API calls
account_id: 2322674

# FortiFlex Program (if using FortiFlex tools)
program_serial_number: "ELAVMS0000003536"
```

**Important**: Create the IAM API user at https://support.fortinet.com/iam with appropriate permissions (Organization Read/ReadWrite scope).

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "org_id": 123456,
  "ou_count": 3,
  "org_units": [
    {
      "id": 100001,
      "name": "North America",
      "desc": "North American customers",
      "parent_id": 123456
    },
    {
      "id": 100002,
      "name": "Customer-Acme",
      "desc": "Acme Corporation",
      "parent_id": 100001
    }
  ]
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `org_id` | Root organization ID (your account) |
| `ou_count` | Number of OUs returned |
| `org_units[].id` | Unique OU identifier (use in other tools) |
| `org_units[].name` | Display name of the OU |
| `org_units[].desc` | Optional description |
| `org_units[].parent_id` | Parent OU ID (for hierarchy) |

## Example Usage

### List All OUs

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-ou-list/1.0.0",
    parameters={}
)
```

### Filter by Parent

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-ou-list/1.0.0",
    parameters={"parent_id": 123456}
)
```

### Search by Name

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-ou-list/1.0.0",
    parameters={"name_pattern": "Acme"}
)
```

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `No credentials found` | Missing API credentials | Set up credential file or environment variables |
| `Authentication failed` | Invalid username/password | Verify API credentials in IAM portal |
| `Authorization denied` | Insufficient permissions | Check IAM user has Organization Read scope |
| `HTTP error: 401` | Token expired or invalid | Re-authenticate (tool handles automatically) |

## Related Tools

- `forticloud-ou-create` - Create new Organization Unit
- `forticloud-ou-update` - Update OU name/description
- `forticloud-ou-delete` - Delete empty OU
- `forticloud-folder-list` - List asset folders
- `forticloud-product-list` - List registered products

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/organization/v1/units/list`
- **Method**: POST
- **Client ID**: `organization`
