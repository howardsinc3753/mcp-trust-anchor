"""
FortiBot.ai Chat - Send chat messages to FortiBot.ai

Provides OpenAI-compatible chat completions via the FortiBot.ai SaaS platform.
Supports multiple models: Claude (haiku/sonnet/opus), DeepSeek, GLM.
"""

import json
from typing import Any, Dict, List, Optional
import requests


# Default configuration
DEFAULT_BASE_URL = "http://fortibot.ai:3000"
DEFAULT_MODEL = "deepseek"
DEFAULT_TIMEOUT = 60


def main(context) -> Dict[str, Any]:
    """
    Send chat messages to FortiBot.ai and receive AI-powered responses.

    Args:
        context: ExecutionContext with attributes:
            - parameters: dict of input parameters
            - credentials: dict of API credentials (optional)
            - metadata: dict of execution metadata

    Returns:
        Dict with chat completion response or error information.
    """
    # Access parameters
    params = getattr(context, "parameters", {})
    credentials = getattr(context, "credentials", {})

    # Get required parameters
    messages = params.get("messages")
    if not messages:
        return {
            "success": False,
            "error": "Missing required parameter: messages"
        }

    # Validate messages format
    if not isinstance(messages, list):
        return {
            "success": False,
            "error": "messages must be an array of message objects"
        }

    for msg in messages:
        if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
            return {
                "success": False,
                "error": "Each message must have 'role' and 'content' fields"
            }

    # Get optional parameters
    model = params.get("model", DEFAULT_MODEL)
    base_url = params.get("base_url", DEFAULT_BASE_URL)

    # Get API key from parameters or credentials
    api_key = params.get("api_key")
    if not api_key and credentials:
        api_key = credentials.get("api_key") or credentials.get("fortibot_api_key")

    if not api_key:
        return {
            "success": False,
            "error": "Missing API key. Provide via 'api_key' parameter or credentials."
        }

    # Build request
    url = f"{base_url.rstrip('/')}/api/v1/chat"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": messages,
        "model": model
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT
        )

        if response.status_code == 401:
            return {
                "success": False,
                "error": "Unauthorized: Invalid API key"
            }

        if response.status_code == 402:
            return {
                "success": False,
                "error": "Payment required: Insufficient credits"
            }

        if response.status_code == 429:
            return {
                "success": False,
                "error": "Rate limited: Too many requests"
            }

        response.raise_for_status()
        data = response.json()

        # Extract the assistant message from choices
        assistant_message = None
        if "choices" in data and len(data["choices"]) > 0:
            assistant_message = data["choices"][0].get("message", {})

        return {
            "success": True,
            "id": data.get("id"),
            "model": data.get("model"),
            "provider": data.get("provider"),
            "message": assistant_message,
            "usage": data.get("usage", {})
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"Request timed out after {DEFAULT_TIMEOUT} seconds"
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "error": f"Connection error: {str(e)}"
        }
    except requests.exceptions.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP error: {str(e)}"
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Invalid JSON response from server"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


# For local testing
if __name__ == "__main__":
    class MockContext:
        def __init__(self, params, creds=None):
            self.parameters = params
            self.credentials = creds or {}
            self.metadata = {}

    # Test with environment variable or hardcoded key
    import os
    test_key = os.environ.get("FORTIBOT_API_KEY", "your-api-key-here")

    ctx = MockContext({
        "messages": [
            {"role": "user", "content": "What is a FortiGate?"}
        ],
        "model": "deepseek",
        "api_key": test_key
    })

    result = main(ctx)
    print(json.dumps(result, indent=2))
