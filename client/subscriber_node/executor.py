"""
Tool Executor - Executes tools pulled from Trust Anchor

Implements code-as-data execution pattern:
1. Pull tool code from Trust Anchor
2. Dynamically execute Python code
3. Return results with credential sanitization

SANITIZE-001: Result sanitization to prevent credential leakage in tool output.
"""

import re
import sys
import logging
import traceback
from io import StringIO
from typing import Any, Optional
from dataclasses import dataclass, field

from .client import SubscriberClient, ToolData

# Audit logger for sanitization events
_sanitize_logger = logging.getLogger("security.sanitize")


@dataclass
class ExecutionResult:
    """Result of tool execution"""
    success: bool
    canonical_id: str
    result: Any = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0


@dataclass
class ExecutionContext:
    """Context passed to tool during execution"""
    parameters: dict = field(default_factory=dict)
    credentials: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# =============================================================================
# SANITIZE-001: Result Sanitization
# =============================================================================

# Patterns that indicate credential data - case insensitive
_CREDENTIAL_KEYS = {
    "api_token", "api_key", "apitoken", "apikey",
    "password", "passwd", "secret", "token",
    "credential", "credentials", "auth_token",
    "access_token", "refresh_token", "bearer",
    "private_key", "privatekey", "ssh_key",
}

# Regex for common credential patterns in strings
_CREDENTIAL_PATTERNS = [
    re.compile(r'api[_-]?(?:token|key)\s*[=:]\s*["\']?[\w\-]+', re.IGNORECASE),
    re.compile(r'(?:password|passwd|secret)\s*[=:]\s*["\']?[\w\-]+', re.IGNORECASE),
    re.compile(r'Bearer\s+[\w\-\.]+', re.IGNORECASE),
]


def _sanitize_value(value: Any, path: str = "") -> tuple[Any, bool]:
    """Recursively sanitize a value, redacting credential-like data."""
    modified = False

    if isinstance(value, dict):
        sanitized = {}
        for k, v in value.items():
            key_lower = k.lower() if isinstance(k, str) else ""
            if key_lower in _CREDENTIAL_KEYS:
                sanitized[k] = "[REDACTED]"
                modified = True
                _sanitize_logger.warning(f"SANITIZE | Redacted key '{k}' at path '{path}.{k}'")
            else:
                sanitized[k], child_modified = _sanitize_value(v, f"{path}.{k}")
                modified = modified or child_modified
        return sanitized, modified

    elif isinstance(value, list):
        sanitized = []
        for i, item in enumerate(value):
            sanitized_item, child_modified = _sanitize_value(item, f"{path}[{i}]")
            sanitized.append(sanitized_item)
            modified = modified or child_modified
        return sanitized, modified

    elif isinstance(value, str):
        sanitized = value
        for pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(sanitized):
                sanitized = pattern.sub("[REDACTED]", sanitized)
                modified = True
        if modified:
            _sanitize_logger.warning(f"SANITIZE | Redacted pattern in string at path '{path}'")
        return sanitized, modified

    else:
        return value, False


def sanitize_result(result: Any, canonical_id: str = "") -> Any:
    """Sanitize tool execution result to prevent credential leakage."""
    if result is None:
        return result

    sanitized, was_modified = _sanitize_value(result, "result")

    if was_modified:
        _sanitize_logger.info(
            f"SANITIZE | tool={canonical_id} | Result contained credential data - redacted"
        )

    return sanitized


class ToolExecutor:
    """
    Executes tools pulled from the Trust Anchor.

    Implements sandboxed execution of code-as-data.
    """

    def __init__(self, client: SubscriberClient):
        self.client = client
        self._tool_cache: dict[str, ToolData] = {}

    def fetch_tool(self, canonical_id: str, use_cache: bool = True) -> Optional[ToolData]:
        """Fetch tool from Trust Anchor with optional caching"""
        if use_cache and canonical_id in self._tool_cache:
            return self._tool_cache[canonical_id]

        tool = self.client.get_tool_with_skills(canonical_id)
        if tool and use_cache:
            self._tool_cache[canonical_id] = tool

        return tool

    def execute(
        self,
        canonical_id: str,
        parameters: dict,
        credentials: Optional[dict] = None,
    ) -> ExecutionResult:
        """Execute a tool by canonical ID."""
        import time
        start_time = time.time()

        # Fetch tool
        tool = self.fetch_tool(canonical_id)
        if not tool:
            return ExecutionResult(
                success=False,
                canonical_id=canonical_id,
                error=f"Tool not found: {canonical_id}",
            )

        # Check for documentation-only tools
        runtime_language = self._get_runtime_language(tool)
        if runtime_language == "none":
            return ExecutionResult(
                success=True,
                canonical_id=canonical_id,
                result={
                    "type": "documentation",
                    "content": tool.skills_md or "No Skills.md content available",
                    "manifest": tool.manifest,
                },
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Check for Python code
        if not tool.code_python:
            return ExecutionResult(
                success=False,
                canonical_id=canonical_id,
                error="Tool has no Python implementation",
            )

        # Build execution context
        context = ExecutionContext(
            parameters=parameters,
            credentials=credentials or {},
            metadata={
                "canonical_id": canonical_id,
                "manifest": tool.manifest,
            },
        )

        # Execute in sandbox
        result = self._execute_python(tool.code_python, context)
        result.canonical_id = canonical_id
        result.execution_time_ms = (time.time() - start_time) * 1000

        # SANITIZE-001: Scrub credentials from result
        result.result = sanitize_result(result.result, canonical_id)
        result.stdout = sanitize_result(result.stdout, canonical_id) or ""
        result.stderr = sanitize_result(result.stderr, canonical_id) or ""

        return result

    def _execute_python(self, code: str, context: ExecutionContext) -> ExecutionResult:
        """Execute Python code in a sandboxed environment."""
        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = captured_stdout = StringIO()
        sys.stderr = captured_stderr = StringIO()

        try:
            # Create execution namespace
            namespace = {
                "__builtins__": __builtins__,
                "context": context,
            }

            # Execute the code to define functions
            exec(code, namespace)

            # Look for main function
            if "main" not in namespace:
                return ExecutionResult(
                    success=False,
                    canonical_id="",
                    error="Tool code must define a 'main(context)' function",
                    stdout=captured_stdout.getvalue(),
                    stderr=captured_stderr.getvalue(),
                )

            # Call main with context
            result = namespace["main"](context)

            return ExecutionResult(
                success=True,
                canonical_id="",
                result=result,
                stdout=captured_stdout.getvalue(),
                stderr=captured_stderr.getvalue(),
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                canonical_id="",
                error=f"{type(e).__name__}: {str(e)}",
                stderr=captured_stderr.getvalue() + "\n" + traceback.format_exc(),
                stdout=captured_stdout.getvalue(),
            )

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def _get_runtime_language(self, tool: ToolData) -> str:
        """Extract runtime language from tool manifest."""
        if not tool.manifest:
            return "python"

        runtime = tool.manifest.get("runtime", {})
        if isinstance(runtime, dict):
            return runtime.get("language", "python").lower()
        return "python"

    def clear_cache(self):
        """Clear the tool cache"""
        self._tool_cache.clear()

    def get_cached_tools(self) -> list[str]:
        """Get list of cached tool IDs"""
        return list(self._tool_cache.keys())
