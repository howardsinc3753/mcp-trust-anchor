# FortiBot.ai List Models

## Purpose

Retrieve the list of available AI models on the FortiBot.ai platform. Use this tool to discover which models are available, their burn rates, and provider information before making chat requests.

## When to Use

- Before calling `fortibot-chat` to see available model options
- To check burn rates for cost planning
- To verify which AI providers are available
- To get the underlying API model IDs

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
  "models": [
    {
      "id": "claude-haiku",
      "provider": "claude",
      "name": "Claude Haiku",
      "description": "Fast & cheap",
      "burn_rate": 0.25,
      "api_model": "claude-3-5-haiku-20241022"
    },
    {
      "id": "claude-sonnet",
      "provider": "claude",
      "name": "Claude Sonnet",
      "description": "Balanced",
      "burn_rate": 1,
      "api_model": "claude-sonnet-4-20250514"
    },
    {
      "id": "claude-opus",
      "provider": "claude",
      "name": "Claude Opus",
      "description": "Most capable",
      "burn_rate": 5,
      "api_model": "claude-opus-4-20250514"
    },
    {
      "id": "deepseek",
      "provider": "deepseek",
      "name": "DeepSeek",
      "description": "Fast & capable",
      "burn_rate": 1,
      "api_model": "deepseek-chat"
    },
    {
      "id": "glm",
      "provider": "glm",
      "name": "GLM 4.7",
      "description": "Flagship model",
      "burn_rate": 1,
      "api_model": "glm-4.7"
    }
  ]
}
```

## Understanding Burn Rates

The `burn_rate` indicates how many tokens are consumed relative to the base rate:
- `0.25` - Most economical (4x fewer tokens burned)
- `1.0` - Standard rate
- `5.0` - Premium rate (5x more tokens burned)

Choose models based on your balance and task complexity.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing API key` | No API key provided | Add `api_key` parameter or configure credentials |
| `Unauthorized: Invalid API key` | API key is invalid | Check API key in FortiBot.ai account |
| `Connection error` | Cannot reach FortiBot.ai | Check network connectivity |

## Related Tools

- `org.ulysses.cloud.fortibot-chat` - Send chat messages
- `org.ulysses.cloud.fortibot-usage` - Check account usage and balance
