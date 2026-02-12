"""
Sample Echo Tool

A simple tool for testing the MCP Trust Anchor framework.
Echoes back the parameters it receives.
"""


def main(context):
    """
    Echo the input message back.

    Args:
        context: ExecutionContext with:
            - parameters.message: The message to echo
            - parameters.uppercase: If True, convert to uppercase
            - parameters.repeat: Number of times to repeat

    Returns:
        dict with echoed message and metadata
    """
    params = context.parameters

    # Get parameters
    message = params.get("message", "")
    uppercase = params.get("uppercase", False)
    repeat = params.get("repeat", 1)

    # Validate
    if not message:
        return {
            "success": False,
            "error": "message parameter is required"
        }

    # Process
    output = message
    if uppercase:
        output = output.upper()

    if repeat > 1:
        output = (output + " ") * repeat
        output = output.strip()

    return {
        "success": True,
        "result": {
            "echoed_message": output,
            "original_message": message,
            "uppercase": uppercase,
            "repeat": repeat,
        },
        "metadata": {
            "tool": "sample-echo",
            "version": "1.0.0",
        }
    }
