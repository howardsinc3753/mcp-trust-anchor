# FortiGate Policy Move - Skills Guide

## Tool Identity
- **Canonical ID:** `org.ulysses.noc.fortigate-policy-move/1.0.0`
- **Domain:** noc
- **Intent:** configure
- **Vendor:** fortinet

## When to Use This Tool

### Primary Use Cases
1. **Move policy to top of list** - Move a policy before the first policy
2. **Move policy after another** - Position policy after a specific rule
3. **Reorder VIP policies** - Ensure VIP-related policies are evaluated first
4. **Fix policy ordering issues** - Correct misplaced rules

### Why Policy Order Matters
FortiGate evaluates firewall policies **top-down** (first match wins):
- More specific rules should be placed **above** general rules
- VIP/DNAT policies typically need to be near the top
- Deny rules often go above allow-all rules
- Implicit deny at bottom catches unmatched traffic

## Parameters

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| target_ip | Yes | string | FortiGate management IP |
| policy_id | Conditional | integer | Policy ID to move |
| policy_name | Conditional | string | Policy name to move (alternative to policy_id) |
| position | Yes | string | "before" or "after" |
| reference_id | Conditional | integer | Reference policy ID |
| reference_name | Conditional | string | Reference policy name (alternative to reference_id) |
| verify_ssl | No | boolean | Verify SSL certificates (default: false) |

## Example Usage

### Move Policy 3 Before Policy 1 (to top)
```json
{
  "target_ip": "192.168.215.15",
  "policy_id": 3,
  "position": "before",
  "reference_id": 1
}
```

### Move Policy by Name
```json
{
  "target_ip": "192.168.215.15",
  "policy_name": "Allow_FMG_VIPs",
  "position": "before",
  "reference_name": "LAN_to_WAN"
}
```

### Move Policy After Another
```json
{
  "target_ip": "192.168.215.15",
  "policy_id": 5,
  "position": "after",
  "reference_id": 2
}
```

### Mixed ID and Name Reference
```json
{
  "target_ip": "192.168.215.15",
  "policy_name": "New_VIP_Policy",
  "position": "before",
  "reference_id": 1
}
```

## Output Example

```json
{
  "success": true,
  "target_ip": "192.168.215.15",
  "policy_id": 3,
  "policy_name": "Allow_FMG_VIPs",
  "position": "before",
  "reference_id": 1,
  "reference_name": "LAN_to_WAN",
  "message": "Moved policy 'Allow_FMG_VIPs' (ID: 3) before 'LAN_to_WAN' (ID: 1)"
}
```

## Common Workflows

### 1. Move VIP Policy to Top
After creating a VIP-based policy, move it to the top of the policy list:
```json
{
  "target_ip": "192.168.215.15",
  "policy_name": "Allow_FMG_VIPs",
  "position": "before",
  "reference_id": 1
}
```

### 2. Insert Policy Between Two Others
To insert policy C between A and B (where B comes after A):
```json
{
  "target_ip": "192.168.215.15",
  "policy_name": "Policy_C",
  "position": "before",
  "reference_name": "Policy_B"
}
```

### 3. Move Policy to Bottom
Move a catchall/logging policy after the last specific rule:
```json
{
  "target_ip": "192.168.215.15",
  "policy_name": "Log_All_Traffic",
  "position": "after",
  "reference_name": "Last_Allow_Rule"
}
```

## Technical Notes

### FortiOS API
This tool uses the FortiOS REST API move action:
```
PUT /api/v2/cmdb/firewall/policy/{id}?action=move&before={ref_id}
PUT /api/v2/cmdb/firewall/policy/{id}?action=move&after={ref_id}
```

### Equivalent CLI
```
config firewall policy
  move <policy_id> before <reference_id>
  move <policy_id> after <reference_id>
end
```

### Policy ID 0
- Policy ID 0 is special - it represents "before first policy"
- To move to absolute top, move before the lowest policy ID
- Use `fortigate-firewall-policy list` to find policy IDs

## Related Tools
- `fortigate-firewall-policy` - Create/delete/list policies
- `fortigate-vip` - Create VIPs for policy destinations

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Policy not found" | Invalid policy_id or policy_name | Verify policy exists with list action |
| "Reference policy not found" | Invalid reference_id or reference_name | Check reference policy exists |
| "Invalid position" | position not 'before' or 'after' | Use valid position value |
