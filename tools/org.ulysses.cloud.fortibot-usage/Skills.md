# FortiBot.ai Usage Stats

## Purpose

Retrieve your FortiBot.ai account usage statistics and credit balance. Use this tool to monitor token consumption, track daily free allowance, and plan your API usage.

## When to Use

- Before heavy API usage to check available credits
- To monitor daily free token consumption
- To check if auto-replenish is configured
- To track lifetime usage for billing/reporting
- To ensure sufficient balance before production workflows

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_key` | string | No* | - | FortiBot.ai API key |
| `base_url` | string | No | `http://fortibot.ai:3000` | API base URL |

*API key can be provided via credentials instead of parameter.

## Example Usage

```json
{
  "api_key": "fb_live_xxx..."
}
```

## Response Format

```json
{
  "success": true,
  "credit_balance": 20894,
  "free_daily_tokens": 500,
  "free_daily_used": 377,
  "free_daily_remaining": 123,
  "total_available": 21017,
  "auto_replenish": true,
  "replenish_threshold": 10000,
  "lifetime_credits_used": 10106
}
```

## Response Fields Explained

| Field | Description |
|-------|-------------|
| `credit_balance` | Purchased/allocated credits in your account |
| `free_daily_tokens` | Daily free token allowance (resets at midnight) |
| `free_daily_used` | Free tokens consumed today |
| `free_daily_remaining` | Free tokens still available today |
| `total_available` | Total tokens you can use (credits + free daily) |
| `auto_replenish` | Whether credits auto-replenish when low |
| `replenish_threshold` | Balance level that triggers auto-replenish |
| `lifetime_credits_used` | Total credits consumed since account creation |

## Token Economics

- **Free Daily Tokens**: 500 tokens free per day
- **Credit Balance**: Purchased credits or organizational allocation
- **Total Available**: Sum of credits + remaining daily free tokens
- **Burn Rates**: Different models burn tokens at different rates (see `fortibot-models`)

## Low Balance Warning

If `total_available` falls below expected usage:
1. Wait for daily reset to get free tokens
2. Add credits to your account
3. Enable auto-replenish for uninterrupted service

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing API key` | No API key provided | Add `api_key` parameter or configure credentials |
| `Unauthorized: Invalid API key` | API key is invalid | Check API key in FortiBot.ai account |
| `Connection error` | Cannot reach FortiBot.ai | Check network connectivity |

## Related Tools

- `org.ulysses.cloud.fortibot-chat` - Send chat messages
- `org.ulysses.cloud.fortibot-models` - List available models and burn rates
