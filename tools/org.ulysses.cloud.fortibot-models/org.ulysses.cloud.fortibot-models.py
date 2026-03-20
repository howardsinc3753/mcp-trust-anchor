"""
FortiBot.ai List Models - List available AI models

Returns the list of available models on FortiBot.ai platform
including model IDs, providers, descriptions, and burn rates.
"""

import json
from typing import Any, Dict
import requests


# Default configuration
DEFAULT_BASE_URL = "http://fortibot.ai:3000"
DEFAULT_TIMEOUT = 30


def main(context) -> Dict[str, Any]:
    """
    List available AI models on FortiBot.ai platform.

    Args:
        context: ExecutionContext with attributes:
            - parameters: dict of input parameters
            - credentials: dict of API credentials (optional)
            - metadata: dict of execution metadata

    Returns:
        Dict with list of available models or error information.
    """
    # Access parameters
    params = getattr(context, "parameters", {})
    credentials = getattr(context, "credentials", {})

    # Get optional parameters
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
    url = f"{base_url.rstrip('/')}/api/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=DEFAULT_TIMEOUT
        )

        if response.status_code == 401:
            return {
                "success": False,
                "error": "Unauthorized: Invalid API key"
            }

        response.raise_for_status()
        data = response.json()

        # Extract models from response
        models = data.get("data", [])

        return {
            "success": True,
            "models": models
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

    import os
    test_key = os.environ.get("FORTIBOT_API_KEY", "your-api-key-here")

    ctx = MockContext({
        "api_key": test_key
    })

    result = main(ctx)
    print(json.dumps(result, indent=2))
