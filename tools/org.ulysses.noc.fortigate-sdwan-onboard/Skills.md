# FortiGate SD-WAN Onboard - Skills Guide

## Overview

Complete SD-WAN site onboarding workflow supporting both **FortiFlex (VM)** and **Standard (hardware)** license types. This tool orchestrates the entire process of bringing new FortiGate spoke sites online.

## License Types - Critical Decision Point

**IMPORTANT**: Before onboarding, determine the license type:

### FortiFlex License (for VM deployments)
- **When to use**: FortiGate-VM in VMware, Hyper-V, AWS, Azure, etc.
- **Workflow**: Provision token → Deploy VM → Apply token → Reboot → Apply config
- **Token application required**: `execute vm-license install <token>`

### Standard License (for hardware devices)
- **When to use**: Physical FortiGate appliances (FortiWiFi-50G-5G, FortiGate-100F, etc.)
- **Workflow**: Power on device → Apply config directly
- **No token application needed** (device is pre-licensed)

## When to Use

- Deploying a new FortiGate (VM or hardware) as an SD-WAN spoke
- Need automated FortiFlex license provisioning (for VMs)
- Want a single tool to handle license + config + tracking
- Onboarding multiple sites with consistent configuration

## Workflows by License Type

### FortiFlex (VM) Workflow
```
┌─────────────────────────────────────────────────────────────┐
│              FORTIFLEX (VM) ONBOARDING WORKFLOW             │
├─────────────────────────────────────────────────────────────┤
│  1. PROVISION-LICENSE                                       │
│     ├── Authenticate to FortiCloud                         │
│     ├── List/Create FortiFlex configuration                │
│     └── Generate VM entitlement (token + serial)           │
│                                                             │
│  2. GENERATE-CONFIG                                         │
│     ├── license_type: fortiflex                            │
│     ├── Include license application command                │
│     ├── Generate FortiOS CLI configuration                 │
│     └── Add to SD-WAN manifest                             │
│                                                             │
│  3. MANUAL DEPLOYMENT                                       │
│     ├── Deploy FortiGate VM                                │
│     ├── execute vm-license install <token>                 │
│     ├── Wait for reboot                                    │
│     └── Apply generated configuration                      │
│                                                             │
│  4. COMPLETE                                                │
│     └── fortigate-sdwan-manifest-tracker action=absorb     │
└─────────────────────────────────────────────────────────────┘
```

### Standard (Hardware) Workflow
```
┌─────────────────────────────────────────────────────────────┐
│            STANDARD (HARDWARE) ONBOARDING WORKFLOW          │
├─────────────────────────────────────────────────────────────┤
│  1. GENERATE-CONFIG                                         │
│     ├── license_type: standard                             │
│     ├── Include device serial info                         │
│     ├── Generate FortiOS CLI configuration                 │
│     └── Add to SD-WAN manifest                             │
│                                                             │
│  2. DEPLOYMENT                                              │
│     ├── Power on hardware device (pre-licensed)            │
│     └── Apply generated configuration directly             │
│                                                             │
│  3. COMPLETE                                                │
│     └── fortigate-sdwan-manifest-tracker action=absorb     │
└─────────────────────────────────────────────────────────────┘
```

## Actions

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `provision-license` | Get FortiFlex token for VM | site_name |
| `generate-config` | Generate SD-WAN config | license_type, site_name, site_id, wan_ip, wan_gateway, lan_ip, lan_network |
| `complete` | Finalize onboarding | target_ip |
| `full-onboard` | Combined workflow | license_type + site params + license-type-specific params |

## Parameters

### Core Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | Workflow action to perform |
| `license_type` | string | **Yes** | **'fortiflex' (VM) or 'standard' (hardware)** |
| `site_name` | string | Yes* | Site hostname (e.g., "Branch1") |
| `site_id` | integer | Yes* | Unique site ID (1-254) |
| `wan_ip` | string | Yes* | WAN interface IP address |
| `wan_gateway` | string | Yes* | WAN default gateway |
| `lan_ip` | string | Yes* | LAN interface gateway IP |
| `lan_network` | string | Yes* | LAN network (CIDR, e.g., "10.1.0.0/16") |

*Required for generate-config and full-onboard actions

### FortiFlex Parameters (for VM deployments)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provision_license` | boolean | true | Whether to provision FortiFlex license |
| `config_id` | integer | - | Existing FortiFlex config ID to use |
| `config_name` | string | - | Name for new FortiFlex config |
| `cpu` | integer | 2 | CPU cores (1, 2, 4, 8, 16, 32) |
| `services` | array | ["FC","UTP","ENT"] | Service codes |
| `fortiflex_token` | string | - | Pre-provisioned token |
| `fortiflex_serial` | string | - | Pre-provisioned serial (FGVMXXXXXX) |
| `fortiflex_config_name` | string | - | FortiFlex configuration name |
| `fortiflex_status` | string | - | License status |
| `fortiflex_end_date` | string | - | License end date |

### Standard License Parameters (for hardware devices)

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_serial` | string | Hardware device serial number (e.g., FW50G5TK25000404) |
| `device_model` | string | Device model (e.g., FortiWiFi-50G-5G) |
| `license_name` | string | License/contract name |
| `license_start_date` | string | License start date (YYYY-MM-DD) |
| `license_end_date` | string | License end date (YYYY-MM-DD) |

### Hub Connection Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `hub_wan_ip` | string | Hub WAN IP (auto-detected from manifest) |
| `hub_loopback` | string | Hub loopback for health check |
| `hub_bgp_loopback` | string | Hub BGP peering loopback |

## Usage Examples

### Full Onboard - FortiFlex (VM Deployment)

```json
{
  "action": "full-onboard",
  "license_type": "fortiflex",
  "site_name": "Branch1-VM",
  "site_id": 1,
  "wan_ip": "10.198.1.2",
  "wan_gateway": "10.198.1.1",
  "lan_ip": "10.1.1.1",
  "lan_network": "10.1.0.0/16",
  "cpu": 2,
  "provision_license": true
}
```

### Full Onboard - Standard (Hardware Device)

```json
{
  "action": "full-onboard",
  "license_type": "standard",
  "site_name": "Branch2-HW",
  "site_id": 2,
  "wan_ip": "10.198.2.2",
  "wan_gateway": "10.198.2.1",
  "lan_ip": "10.2.1.1",
  "lan_network": "10.2.0.0/16",
  "device_serial": "FW50G5TK25000404",
  "device_model": "FortiWiFi-50G-5G",
  "license_name": "50G-Lab-FortiGate-SE",
  "license_end_date": "2026-10-21"
}
```

### Provision License Only (FortiFlex)

```json
{
  "action": "provision-license",
  "site_name": "Branch3",
  "cpu": 2,
  "config_name": "sdwan-spoke-2cpu-ent"
}
```

### Generate Config with Pre-provisioned Token (FortiFlex)

```json
{
  "action": "generate-config",
  "license_type": "fortiflex",
  "site_name": "Branch3",
  "site_id": 3,
  "wan_ip": "10.198.3.2",
  "wan_gateway": "10.198.3.1",
  "lan_ip": "10.3.1.1",
  "lan_network": "10.3.0.0/16",
  "fortiflex_token": "58A7B75F319C5518CD04",
  "fortiflex_serial": "FGVMMLTM26000192"
}
```

### Generate Config for Hardware Device (Standard)

```json
{
  "action": "generate-config",
  "license_type": "standard",
  "site_name": "Branch4",
  "site_id": 4,
  "wan_ip": "10.198.4.2",
  "wan_gateway": "10.198.4.1",
  "lan_ip": "10.4.1.1",
  "lan_network": "10.4.0.0/16",
  "device_serial": "FW50G5TK25000404",
  "device_model": "FortiWiFi-50G-5G"
}
```

### Complete Onboarding

```json
{
  "action": "complete",
  "target_ip": "10.198.1.2"
}
```

## Output Examples

### full-onboard Response - FortiFlex (VM)

```json
{
  "success": true,
  "site_name": "Branch1",
  "site_id": 1,
  "license_type": "fortiflex",
  "steps_completed": ["provision-license", "generate-config"],
  "steps_remaining": [
    "1. Deploy FortiGate VM",
    "2. Apply license: execute vm-license install 58A7B75F319C5518CD04",
    "3. Wait for device reboot",
    "4. Apply configuration from: C:/ProgramData/Ulysses/config/blueprints/Branch1_onboard_config.txt",
    "5. Verify connectivity",
    "6. Complete onboarding: fortigate-sdwan-manifest-tracker action=absorb target_ip=10.198.1.2"
  ],
  "license": {
    "type": "fortiflex",
    "serial": "FGVMMLTM26000192",
    "token": "58A7B75F319C5518CD04",
    "requires_token_application": true,
    "license_command": "execute vm-license install 58A7B75F319C5518CD04"
  },
  "license_command": "execute vm-license install 58A7B75F319C5518CD04",
  "config_path": "C:/ProgramData/Ulysses/config/blueprints/Branch1_onboard_config.txt",
  "device_key": "spoke_onboard_1"
}
```

### full-onboard Response - Standard (Hardware)

```json
{
  "success": true,
  "site_name": "Branch2",
  "site_id": 2,
  "license_type": "standard",
  "steps_completed": ["generate-config"],
  "steps_remaining": [
    "1. Power on hardware device (Serial: FW50G5TK25000404)",
    "2. Apply configuration from: C:/ProgramData/Ulysses/config/blueprints/Branch2_onboard_config.txt",
    "   (Hardware devices are pre-licensed - no token application needed)",
    "3. Verify connectivity",
    "4. Complete onboarding: fortigate-sdwan-manifest-tracker action=absorb target_ip=10.198.2.2"
  ],
  "license": {
    "type": "standard",
    "device_serial": "FW50G5TK25000404",
    "device_model": "FortiWiFi-50G-5G",
    "requires_token_application": false,
    "note": "Hardware device is pre-licensed. Apply config directly."
  },
  "requires_token_application": false,
  "config_path": "C:/ProgramData/Ulysses/config/blueprints/Branch2_onboard_config.txt",
  "device_key": "spoke_onboard_2"
}
```

### provision-license Response (FortiFlex only)

```json
{
  "success": true,
  "step": "provision-license",
  "site_name": "Branch1",
  "config_id": 53713,
  "fortiflex": {
    "serial": "FGVMMLTM26000192",
    "token": "58A7B75F319C5518CD04",
    "config_id": 53713,
    "status": "PENDING",
    "token_status": "NOTUSED",
    "end_date": "2027-05-29T00:00:00"
  },
  "license_command": "execute vm-license install 58A7B75F319C5518CD04",
  "next_step": "Apply license to FortiGate VM, then run 'generate-config' action"
}
```

## Prerequisites

### FortiFlex Credentials

Configure `C:\ProgramData\Ulysses\config\forticloud_credentials.yaml`:

```yaml
api_username: "YOUR-API-USER-ID"
api_password: "your-api-password"
program_serial_number: "ELAVMS0000003536"
account_id: 2322674  # Required for MSSP programs
```

### FortiGate Credentials

For the `complete` action, configure device in `fortigate_credentials.yaml`:

```yaml
devices:
  branch1:
    host: "10.198.1.2"
    api_token: "your-api-token"
    verify_ssl: false
default_lookup:
  "10.198.1.2": "branch1"
```

## Complete Deployment Workflow

### Step-by-Step Process

```
1. Run full-onboard tool
   └── Provisions FortiFlex token
   └── Generates basic config
   └── Adds to manifest as "onboarding"

2. Deploy FortiGate VM in your environment
   └── VMware, Hyper-V, KVM, Azure, AWS, etc.

3. Access FortiGate console/SSH and apply license
   └── execute vm-license install <token>
   └── Device will reboot

4. After reboot, apply full SD-WAN config
   └── Option A: Use generated config file
   └── Option B: Use fortigate-sdwan-blueprint-planner for full template

5. Complete onboarding
   └── Run fortigate-sdwan-manifest-tracker action=absorb
   └── This captures full device config into manifest
```

### Using with Blueprint Planner

For complete SD-WAN configuration (not just basics):

```
1. sdwan-onboard action=provision-license
   └── Get FortiFlex token

2. sdwan-blueprint-planner action=generate-template
   └── Get CSV template with recommended values

3. Fill in CSV with:
   └── Site-specific values
   └── FortiFlex token from step 1

4. sdwan-blueprint-planner action=plan-site
   └── Generate complete FortiOS config

5. Deploy and apply as above
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `No FortiCloud credentials found` | Missing forticloud_credentials.yaml | Configure credentials |
| `No program_serial_number configured` | Missing program SN | Add to credential file |
| `Could not determine or create config_id` | FortiFlex API error | Check program balance |
| `Missing required field` | Incomplete parameters | Provide all required params |

## Related Tools

### FortiFlex Tools
- `fortiflex-programs-list` - List programs and point balance
- `fortiflex-config-list` - List available configurations
- `fortiflex-config-create` - Create new configurations
- `fortiflex-token-create` - Generate license tokens

### SD-WAN Tools
- `fortigate-sdwan-blueprint-planner` - Full template-based config
- `fortigate-sdwan-manifest-tracker` - Device inventory tracking
- `fortigate-config-push` - Push config to devices

## FortiFlex API Reference

### Authentication
- **Endpoint**: `https://customerapiauth.fortinet.com/api/v1/oauth/token/`
- **Client ID**: `flexvm`
- **Grant Type**: `password`

### VM Entitlements
- **Endpoint**: `https://support.fortinet.com/ES/api/fortiflex/v2/entitlements/vm/create`
- **Used For**: FortiGate-VM, FortiManager-VM, FortiAnalyzer-VM

### Applying License to FortiGate

```bash
# Via FortiGate CLI
execute vm-license install <token>

# Example
execute vm-license install EF0AAE0ADA1B577453E3
```

The device will reboot after license application.
