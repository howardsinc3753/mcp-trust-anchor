# FortiBot.ai Chat

## Purpose

Send chat messages to FortiBot.ai and receive AI-powered responses specialized in Fortinet products and cybersecurity. This tool provides an OpenAI-compatible chat completions interface to the FortiBot.ai SaaS platform.

## When to Use

- Ask questions about FortiGate configuration and troubleshooting
- Get help with FortiOS CLI commands
- Design network security architectures
- Configure VPNs (IPsec/SSL)
- Implement SD-WAN solutions
- Query FortiManager/FortiAnalyzer best practices
- General cybersecurity guidance

## Available Models

| Model | Provider | Burn Rate | Description |
|-------|----------|-----------|-------------|
| `claude-haiku` | Claude | 0.25 | Fast & cheap |
| `claude-sonnet` | Claude | 1.0 | Balanced |
| `claude-opus` | Claude | 5.0 | Most capable |
| `deepseek` | DeepSeek | 1.0 | Fast & capable (default) |
| `glm` | GLM | 1.0 | Flagship model |

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `messages` | array | Yes | - | Array of message objects with `role` and `content` |
| `model` | string | No | `deepseek` | Model to use for completion |
| `api_key` | string | No* | - | FortiBot.ai API key |
| `base_url` | string | No | `http://fortibot.ai:3000` | API base URL |

*API key can be provided via credentials instead of parameter.

## Message Format

Each message object must have:
- `role`: One of `system`, `user`, or `assistant`
- `content`: The message text

## Example Usage

### Simple Question
```json
{
  "messages": [
    {"role": "user", "content": "How do I configure a static route on FortiGate?"}
  ],
  "model": "deepseek",
  "api_key": "fb_live_xxx..."
}
```

### With System Prompt
```json
{
  "messages": [
    {"role": "system", "content": "You are a FortiGate CLI expert. Respond with only CLI commands."},
    {"role": "user", "content": "Create a static route to 10.0.0.0/8 via gateway 192.168.1.1"}
  ],
  "model": "claude-sonnet"
}
```

### Multi-turn Conversation
```json
{
  "messages": [
    {"role": "user", "content": "What ports does FortiGate use for management?"},
    {"role": "assistant", "content": "FortiGate uses: HTTPS (443), SSH (22), SNMP (161/162), FortiManager (541)."},
    {"role": "user", "content": "How do I change the HTTPS port?"}
  ]
}
```

## Response Format

```json
{
  "success": true,
  "id": "chat-1234567890",
  "model": "deepseek",
  "provider": "deepseek",
  "message": {
    "role": "assistant",
    "content": "To configure a static route on FortiGate..."
  },
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 150,
    "total_tokens": 200,
    "tokens_burned": 200,
    "credit_balance": 19800
  }
}
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing API key` | No API key provided | Add `api_key` parameter or configure credentials |
| `Unauthorized: Invalid API key` | API key is invalid | Check API key in FortiBot.ai account |
| `Payment required: Insufficient credits` | Account has no credits | Add credits to FortiBot.ai account |
| `Rate limited` | Too many requests | Wait and retry |
| `Connection error` | Cannot reach FortiBot.ai | Check network connectivity |

## Token Economics

- Each API call burns tokens from your account balance
- Burn rate varies by model (see Available Models table)
- Monitor usage with the `fortibot-usage` tool
- Free daily tokens available (500/day)

## Related Tools

- `org.ulysses.cloud.fortibot-models` - List available models
- `org.ulysses.cloud.fortibot-usage` - Check account usage and balance
