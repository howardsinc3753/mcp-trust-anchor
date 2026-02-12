# API Reference

This document describes the Trust Anchor HTTP API endpoints.

## Base URL

```
http://<server>:8000
```

## Authentication

Publisher endpoints require the `X-Publisher-Key` header:

```
X-Publisher-Key: your-publisher-key
```

## Health Check

### GET /health

Check server health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0"
}
```

## Keys API

### GET /keys/public

Get the Trust Anchor public key for signature verification.

**Response:**
```json
{
  "public_key": "-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----",
  "version": "1",
  "algorithm": "RSA-2048-PKCS1v15-SHA256"
}
```

## Tools API

### GET /tools/list

List all certified tools.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `domain` | string | Filter by domain |
| `vendor` | string | Filter by vendor |
| `intent` | string | Filter by intent |

**Response:**
```json
{
  "tools": [
    {
      "canonical_id": "org.example.tool/1.0.0",
      "name": "Tool Name",
      "version": "1.0.0",
      "description": "Tool description",
      "domain": "noc",
      "vendor": "example",
      "status": "certified"
    }
  ],
  "total": 1
}
```

### GET /tools/get/{canonical_id}

Get a specific tool by canonical ID.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `canonical_id` | string | Tool canonical ID (URL encoded) |

**Response:**
```json
{
  "canonical_id": "org.example.tool/1.0.0",
  "name": "Tool Name",
  "version": "1.0.0",
  "manifest": {...},
  "code_python": "def main(context):...",
  "skills_md": "# Tool Skills\n...",
  "status": "certified"
}
```

### GET /tools/get/{canonical_id}/signature

Get signature data for a tool.

**Response:**
```json
{
  "signature": "base64-encoded-signature",
  "code_hash": "sha256-hash-of-code",
  "signing_payload": {
    "canonical_id": "org.example.tool/1.0.0",
    "version": "1.0.0",
    "code_hash_sha256": "abc123...",
    "signed_at": "2024-01-15T10:30:00Z"
  },
  "signed_at": "2024-01-15T10:30:00Z",
  "signed_by_key": "v1",
  "status": "valid"
}
```

## Publisher API

All publisher endpoints require `X-Publisher-Key` header.

### POST /publisher/submit-tool

Submit a new tool for registration.

**Request Body:**
```json
{
  "manifest": {
    "canonical_id": "org.example.tool/1.0.0",
    "name": "Tool Name",
    "version": "1.0.0",
    "description": "...",
    "metadata": {...},
    "parameters": [...],
    "capabilities": {...}
  },
  "code_python": "def main(context):...",
  "skills_md": "# Skills\n..."
}
```

**Response:**
```json
{
  "status": "submitted",
  "canonical_id": "org.example.tool/1.0.0",
  "message": "Tool submitted successfully"
}
```

### POST /publisher/certify/{canonical_id}

Sign and certify a submitted tool.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `canonical_id` | string | Tool canonical ID (URL encoded) |

**Response:**
```json
{
  "status": "certified",
  "canonical_id": "org.example.tool/1.0.0",
  "signature": "base64-signature",
  "code_hash": "sha256-hash",
  "signed_at": "2024-01-15T10:30:00Z"
}
```

### GET /publisher/status

Get publisher API status.

**Response:**
```json
{
  "status": "active",
  "tools_pending": 0,
  "tools_certified": 5
}
```

## Subscribers API

### POST /subscribers/register

Register a new subscriber endpoint.

**Request Body:**
```json
{
  "endpoint_id": "unique-endpoint-id",
  "hostname": "workstation.local",
  "platform": "Windows",
  "capabilities": ["python"]
}
```

**Response:**
```json
{
  "status": "registered",
  "endpoint_id": "unique-endpoint-id",
  "registered_at": "2024-01-15T10:30:00Z"
}
```

### POST /subscribers/heartbeat

Send heartbeat from subscriber.

**Request Body:**
```json
{
  "endpoint_id": "unique-endpoint-id",
  "status": "healthy"
}
```

**Response:**
```json
{
  "status": "ok",
  "server_time": "2024-01-15T10:30:00Z"
}
```

## Runbooks API

### GET /runbooks/list

List available runbooks.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `domain` | string | Filter by domain |
| `vendor` | string | Filter by vendor |
| `intent` | string | Filter by intent |

**Response:**
```json
{
  "runbooks": [
    {
      "runbook_id": "org.example.runbook/1.0.0",
      "name": "Runbook Name",
      "description": "...",
      "steps": 5
    }
  ],
  "total": 1
}
```

### GET /runbooks/get/{runbook_id}

Get a specific runbook.

**Response:**
```json
{
  "runbook_id": "org.example.runbook/1.0.0",
  "name": "Runbook Name",
  "description": "...",
  "steps": [
    {
      "tool_id": "org.example.tool/1.0.0",
      "parameters": {...},
      "on_failure": "abort"
    }
  ]
}
```

## Error Responses

All endpoints may return error responses:

### 400 Bad Request
```json
{
  "detail": "Invalid request: missing required field 'canonical_id'"
}
```

### 401 Unauthorized
```json
{
  "detail": "Invalid or missing X-Publisher-Key"
}
```

### 404 Not Found
```json
{
  "detail": "Tool not found: org.example.tool/1.0.0"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error",
  "error_id": "abc123"
}
```

## Rate Limiting

Currently no rate limiting is enforced. Future versions may add:
- Per-endpoint limits
- Per-key limits for publisher API

## CORS

CORS is enabled for all origins by default. Configure in production:

```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["X-Publisher-Key"]
)
```
