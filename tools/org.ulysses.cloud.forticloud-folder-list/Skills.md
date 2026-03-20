# FortiCloud Folder List Skills

## How to Call

Use this tool when:
- User wants to see asset folder structure in FortiCloud
- User needs folder IDs to organize products
- User is setting up asset management hierarchy
- User needs to find where products are located

**Example prompts:**
- "List my FortiCloud asset folders"
- "Show me the folder structure in asset management"
- "What folders do I have for organizing devices?"

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `account_id` | integer | No* | - | Account ID (*required for Org scope users) |
| `api_username` | string | No | from config | Override credential file |
| `api_password` | string | No | from config | Override credential file |

## Example Usage

### List All Folders

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-folder-list/1.0.0",
    parameters={}
)
```

### List Folders for Specific Account

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-folder-list/1.0.0",
    parameters={"account_id": 12345678}
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "folder_count": 3,
  "folders": [
    {
      "folder_id": 1001,
      "folder_name": "Production",
      "folder_path": "/My Assets/Production",
      "parent_folder_id": 1000
    },
    {
      "folder_id": 1002,
      "folder_name": "Development",
      "folder_path": "/My Assets/Development",
      "parent_folder_id": 1000
    }
  ]
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `folder_id` | Unique folder ID (use in other tools) |
| `folder_name` | Display name |
| `folder_path` | Full path from root |
| `parent_folder_id` | Parent folder ID |

## Related Tools

- `forticloud-folder-create` - Create new folders
- `forticloud-product-list` - List products in folders
- `forticloud-product-folder` - Move products to folders

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/registration/v3/folders/list`
- **Method**: POST
- **Client ID**: `assetmanagement`
