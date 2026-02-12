# Sample Echo Tool - Skills Guide

## Overview

The Sample Echo tool is a simple utility for testing the MCP Trust Anchor framework. It echoes back the parameters it receives, optionally transforming them.

## When to Use

Use this tool to:
- Test that tool execution is working
- Verify signature verification is functioning
- Debug MCP Bridge connectivity

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| message | string | Yes | - | The message to echo back |
| uppercase | boolean | No | false | Convert message to uppercase |
| repeat | integer | No | 1 | Number of times to repeat the message |

## Example Usage

### Basic Echo
```json
{
  "message": "Hello, Trust Anchor!"
}
```

Response:
```json
{
  "success": true,
  "result": {
    "echoed_message": "Hello, Trust Anchor!",
    "original_message": "Hello, Trust Anchor!",
    "uppercase": false,
    "repeat": 1
  }
}
```

### Uppercase Echo
```json
{
  "message": "hello world",
  "uppercase": true
}
```

Response:
```json
{
  "success": true,
  "result": {
    "echoed_message": "HELLO WORLD",
    "original_message": "hello world",
    "uppercase": true,
    "repeat": 1
  }
}
```

### Repeated Message
```json
{
  "message": "echo",
  "repeat": 3
}
```

Response:
```json
{
  "success": true,
  "result": {
    "echoed_message": "echo echo echo",
    "original_message": "echo",
    "repeat": 3
  }
}
```

## No Credentials Required

This tool does not require any credentials. It's purely for testing purposes.

## Security Notes

- This tool has no network access
- This tool has no file system access
- Safe to use for testing in any environment
