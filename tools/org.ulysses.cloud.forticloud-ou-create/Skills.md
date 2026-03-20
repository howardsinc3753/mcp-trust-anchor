# FortiCloud OU Create Skills

## How to Call

Use this tool when:
- User needs to create a new customer organization in FortiCloud
- User is onboarding a new MSSP customer
- User needs to set up multi-tenant hierarchy
- User wants to create sub-OUs for organizational structure

**Example prompts:**
- "Create a new organization for Acme Corporation"
- "Add a customer OU under North America"
- "Set up a new tenant in FortiCloud for customer XYZ"
- "Create an OU called 'West Region' under parent 123456"

## Prerequisites

1. **FortiCloud IAM API User** with Organization scope
2. **Permissions**: ReadWrite or Admin access to Organization portal
3. **Parent OU ID**: Use `forticloud-ou-list` to find the parent ID
4. **Client ID**: `organization`

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-API-USER-ID"
api_password: "your-api-password"
```

**Note**: This is a **write operation** that creates persistent data in FortiCloud. Created OUs cannot be deleted unless empty.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `parent_id` | integer | **Yes** | - | Parent OU ID (use forticloud-ou-list) |
| `name` | string | **Yes** | - | Name for the new OU |
| `desc` | string | No | - | Optional description |
| `api_username` | string | No | - | Override credential file |
| `api_password` | string | No | - | Override credential file |

## Typical Workflow

1. **List existing OUs** to find parent ID:
   ```python
   execute_certified_tool(
       canonical_id="org.ulysses.cloud.forticloud-ou-list/1.0.0",
       parameters={}
   )
   ```

2. **Create new OU** under parent:
   ```python
   execute_certified_tool(
       canonical_id="org.ulysses.cloud.forticloud-ou-create/1.0.0",
       parameters={
           "parent_id": 123456,
           "name": "Customer-Acme",
           "desc": "Acme Corporation - Enterprise customer"
       }
   )
   ```

3. **Create sub-OUs** for organization:
   ```python
   # Create regional sub-OUs
   execute_certified_tool(
       canonical_id="org.ulysses.cloud.forticloud-ou-create/1.0.0",
       parameters={
           "parent_id": 100001,  # Customer-Acme OU ID
           "name": "Acme-West",
           "desc": "Acme West Coast offices"
       }
   )
   ```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "org_id": 123456,
  "created_ou": {
    "id": 100001,
    "name": "Customer-Acme",
    "desc": "Acme Corporation - Enterprise customer",
    "parent_id": 123456
  }
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `org_id` | Root organization ID |
| `created_ou.id` | **Important**: New OU ID for subsequent operations |
| `created_ou.name` | OU name as created |
| `created_ou.desc` | OU description |
| `created_ou.parent_id` | Parent OU ID |

## Naming Conventions

Recommended naming patterns for MSSP operations:

| Pattern | Example | Use Case |
|---------|---------|----------|
| `Customer-{name}` | `Customer-Acme` | Top-level customer OU |
| `{customer}-{region}` | `Acme-West` | Regional sub-OU |
| `{customer}-{site}` | `Acme-HQ` | Site-specific OU |
| `{customer}-{env}` | `Acme-Prod` | Environment separation |

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Missing required parameter: parent_id` | No parent ID provided | Use forticloud-ou-list first |
| `Missing required parameter: name` | No name provided | Provide OU name |
| `Invalid name` | Name contains invalid characters | Remove special characters |
| `Authentication failed` | Invalid credentials | Check API credentials |
| `Authorization denied` | Insufficient permissions | Need ReadWrite/Admin scope |
| `Duplicate name` | OU with same name exists | Use different name |

## Security Notes

- Names are validated to prevent injection attacks
- Maximum name length: 255 characters
- Forbidden characters: `< > ; & | \` $`

## Related Tools

- `forticloud-ou-list` - List OUs (get parent_id)
- `forticloud-ou-update` - Update OU name/description
- `forticloud-ou-delete` - Delete empty OU
- `forticloud-folder-create` - Create asset folder in new OU

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/organization/v1/units/create`
- **Method**: POST
- **Client ID**: `organization`
- **Required Scope**: ReadWrite or Admin
