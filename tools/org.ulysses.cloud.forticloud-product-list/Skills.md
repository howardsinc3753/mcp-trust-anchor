# FortiCloud Product List Skills

## Overview

List registered products/assets from FortiCloud Asset Management. Returns products with their entitlements, support coverage status, and organizational location.

## When to Use

Use this tool when:
- Auditing registered assets across the organization
- Finding products with expiring support contracts
- Searching for specific devices by serial number
- Generating inventory reports
- Checking entitlement status before renewals

**Example prompts:**
- "List all registered FortiGates in FortiCloud"
- "Find products expiring in the next 30 days"
- "Show me the inventory for account 2322674"
- "Search for serial number FGT60F1234567890"

## Prerequisites

1. **FortiCloud API User** - IAM user with Asset Management scope
2. **Permissions** - Read access required
3. **Client ID**: `assetmanagement`
4. **Account ID** - Required for Organization scope API users (auto-loaded from config)

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `serial_number` | string | No | "*" | Serial number or pattern (e.g., "FGT*") |
| `expire_before` | string | No | - | ISO 8601 date - find expiring products |
| `status` | string | No | - | "Registered" or "Pending" |
| `product_model` | string | No | - | Filter by model name |
| `account_id` | integer | No | from config | Account ID (Org scope) |
| `api_username` | string | No | from config | Override credentials |
| `api_password` | string | No | from config | Override credentials |

## Typical Workflows

### 1. List All Products

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-product-list/1.0.0",
    parameters={}
)
```

### 2. Find Expiring Contracts

```python
# Find products expiring before March 2026
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-product-list/1.0.0",
    parameters={
        "expire_before": "2026-03-01T00:00:00-08:00"
    }
)
```

### 3. Search by Serial Number

```python
# Find all FortiGate 60F devices
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-product-list/1.0.0",
    parameters={
        "serial_number": "FGT60F*"
    }
)
```

### 4. Filter by Product Model

```python
execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-product-list/1.0.0",
    parameters={
        "product_model": "FortiGate 90D"
    }
)
```

## Interpreting Results

### Success Response

```json
{
  "success": true,
  "product_count": 3,
  "products": [
    {
      "serial_number": "FGT60F1234567890",
      "product_model": "FortiGate 60F",
      "status": "Registered",
      "description": "Main Office Firewall",
      "folder_id": 1551234,
      "folder_path": "/Customer ABC/Production",
      "account_id": 2322674,
      "registration_date": "2024-01-15T10:30:00-08:00",
      "is_decommissioned": false,
      "product_model_eor": "2028-12-31T00:00:00",
      "product_model_eos": "2029-12-31T00:00:00",
      "entitlements": [
        {
          "type": "FortiCare Premium",
          "level": "Premium",
          "start_date": "2024-01-15T00:00:00-08:00",
          "end_date": "2027-01-15T00:00:00-08:00"
        },
        {
          "type": "Unified Threat Protection",
          "level": "Bundle",
          "start_date": "2024-01-15T00:00:00-08:00",
          "end_date": "2027-01-15T00:00:00-08:00"
        }
      ]
    }
  ]
}
```

### Field Meanings

| Field | Description |
|-------|-------------|
| `serial_number` | Unique device identifier |
| `product_model` | Hardware/VM model |
| `status` | "Registered" or "Pending" |
| `folder_path` | Asset folder location |
| `registration_date` | When asset was registered |
| `is_decommissioned` | True if device retired |
| `product_model_eor` | End of Registration date |
| `product_model_eos` | End of Support date |
| `entitlements` | Active support contracts |

### Entitlement Types

| Type | Description |
|------|-------------|
| FortiCare Premium | 24x7 support with advanced RMA |
| FortiCare Essential | 8x5 basic support |
| Unified Threat Protection | Security bundle (AV, IPS, Web) |
| Enterprise Protection | Full security + cloud services |

## Error Handling

| Error | Meaning | Suggestion |
|-------|---------|------------|
| `No credentials found` | Missing API credentials | Configure credentials |
| `accountId required` | Org scope without account_id | Add to config |
| `Invalid filter` | Bad search parameters | Check parameter format |
| `No products found` | Query returned empty | Adjust search criteria |

## Use Cases

### Inventory Audit

```python
# Get all products for a full inventory
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-product-list/1.0.0",
    parameters={"serial_number": "*"}
)

for product in result["products"]:
    print(f"{product['serial_number']}: {product['product_model']}")
```

### Renewal Planning

```python
# Find products expiring in next 90 days
from datetime import datetime, timedelta

expire_date = (datetime.now() + timedelta(days=90)).isoformat()
result = execute_certified_tool(
    canonical_id="org.ulysses.cloud.forticloud-product-list/1.0.0",
    parameters={"expire_before": expire_date}
)
```

## Related Tools

- `forticloud-folder-list` - List asset folders
- `forticloud-folder-create` - Create new folders
- `forticloud-ou-list` - List organization units
- `fortiflex-token-create` - Create VM licenses

## API Reference

- **Auth Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **API Endpoint**: `https://support.fortinet.com/ES/api/registration/v3/products/list`
- **Method**: POST
- **Client ID**: `assetmanagement`
- **Required Scope**: Read
