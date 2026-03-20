"""
FortiBot.ai Usage Stats - Get account usage and credit balance

Returns account usage statistics including credit balance,
daily free allowance, and lifetime usage metrics.
"""

import json
from typing import Any, Dict
import requests


# Default configuration
DEFAULT_BASE_URL = "http://fortibot.ai:3000"
DEFAULT_TIMEOUT = 30


def main(context) -> Dict[str, Any]:
    """
    Get FortiBot.ai account usage statistics and credit balance.

    Args:
        context: ExecutionContext with attributes:
            - parameters: dict of input parameters
            - credentials: dict of API credentials (optional)
            - metadata: dict of execution metadata

    Returns:
        Dict with usage statistics or error information.
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
    url = f"{base_url.rstrip('/')}/api/v1/usage"
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

        return {
            "success": True,
            "credit_balance": data.get("credit_balance", 0),
            "free_daily_tokens": data.get("free_daily_tokens", 0),
            "free_daily_used": data.get("free_daily_used", 0),
            "free_daily_remaining": data.get("free_daily_remaining", 0),
            "total_available": data.get("total_available", 0),
            "auto_replenish": data.get("auto_replenish", False),
            "replenish_threshold": data.get("replenish_threshold", 0),
            "lifetime_credits_used": data.get("lifetime_credits_used", 0)
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
