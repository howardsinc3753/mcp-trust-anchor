# FortiCloud Folder Create Skills

## Overview

Create asset folders in FortiCloud Asset Management. Folders help organize assets by customer, location, project, or any other logical grouping.

## When to Use

Use this tool when:
- Setting up a new customer environment in FortiCloud
- Organizing assets into logical groups (by site, department, etc.)
- Creating nested folder hierarchies for complex organizations
- Automating customer onboarding workflows

**Example prompts:**
- "Create a folder called 'Customer ABC' in FortiCloud"
- "Add a new asset folder for the Seattle office"
- "Set up a subfolder under 'Production' for FortiGates"

## Prerequisites

1. **FortiCloud API User** - IAM user with Asset Management scope
2. **Permissions** - ReadWrite or Admin access required
3. **Client ID**: `assetmanagement`
4. **Account ID** - Required for Organization scope API users (auto-loaded from config)

## Configuration

Add credentials to `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-API-USER-ID"
api_password: "your-api-password"
account_id: 2322674  # Required for Org-scope API users
```

**Note**: This is a **write operation** that creates persistent folders in FortiCloud Asset Management.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `folder_name` | string | **Yes** | - | Name of the folder to create |
| `parent_folder_id` | integer | No | - | Parent folder ID for nested folders |
| `account_id` | integer | No | from config | Account ID (Org scope) |
| `api_username` | string | No | from config | Override credentials |
| `api_password` | string | No | from config | Override credentials |

## Typical Workflow

### 1. Create Root-Level Folder

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-folder-create/1.0.0",
    parameters={
        "folder_name": "Customer ABC"
    }
)
```

### 2. Create Nested Folder

```python
# First, list existing folders to get parent_folder_id
folders = execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-folder-list/1.0.0",
    parameters={}
)

# Find parent folder ID
parent_id = None
for folder in folders["folders"]:
    if folder["folder_name"] == "Customer ABC":
        parent_id = folder["folder_id"]
        break

# Create subfolder
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-folder-create/1.0.0",
    parameters={
        "folder_name": "Production",
        "parent_folder_id": parent_id
    }
)
```

## Example Usage

### Create Customer Folder

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-folder-create/1.0.0",
    parameters={
        "folder_name": "Acme Corporation"
    }
)
```

### Create Site Subfolder

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-folder-create/1.0.0",
    parameters={
        "folder_name": "NYC Office",
        "parent_folder_id": 1234567
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "message": "Folder 'Customer ABC' created successfully",
  "folder": {
    "folder_id": 1551234,
    "folder_name": "Customer ABC",
    "folder_path": "/Customer ABC",
    "parent_folder_id": null
  }
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `folder_id` | Unique ID for the new folder (use for API operations) |
| `folder_name` | Display name of the folder |
| `folder_path` | Full path from root |
| `parent_folder_id` | ID of parent folder (null for root-level) |

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `Missing folder_name` | No folder name provided | Provide folder_name parameter |
| `Folder already exists` | Duplicate folder name | Use different name or check existing folders |
| `Invalid parent folder` | Parent folder ID not found | Verify parent_folder_id with folder-list |
| `Permission denied` | Insufficient API permissions | Need ReadWrite or Admin scope |
| `accountId required` | Using Org scope without account_id | Add account_id to config or parameters |

## Related Tools

- `forticloud-folder-list` - List existing folders
- `forticloud-ou-list` - List organization units
- `forticloud-ou-create` - Create new OUs
- `forticloud-product-list` - List registered products

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/registration/v3/folders/create`
- **Method**: POST
- **Client ID**: `assetmanagement`
- **Required Scope**: ReadWrite or Admin
