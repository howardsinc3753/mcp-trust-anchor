"""
Subscriber Client - Communicates with Trust Anchor

Fetches tool manifests, code, and skills from the Trust Anchor.
Handles subscriber registration and heartbeat for MCP Bridge.
"""

import httpx
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class ToolData:
    """Container for tool data retrieved from Trust Anchor"""
    canonical_id: str
    manifest: dict
    code_python: Optional[str] = None
    skills_md: Optional[str] = None


class SubscriberClient:
    """Client for communicating with MCP Trust Anchor"""

    def __init__(
        self,
        master_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        verify: bool = False  # HTTP mode for v1
    ):
        self.master_url = master_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout, verify=verify)

    def health_check(self) -> dict:
        """Check Trust Anchor health"""
        response = self._client.get(f"{self.master_url}/health")
        response.raise_for_status()
        return response.json()

    def list_tools(
        self,
        shelf: Optional[str] = None,
        domain: Optional[str] = None,
        vendor: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[dict]:
        """List available tools with optional filters"""
        params = {}
        if shelf:
            params["shelf"] = shelf
        if domain:
            params["domain"] = domain
        if vendor:
            params["vendor"] = vendor
        if intent:
            params["intent"] = intent

        response = self._client.get(f"{self.master_url}/tools", params=params)
        response.raise_for_status()
        return response.json().get("tools", [])

    def get_tool(self, canonical_id: str) -> Optional[ToolData]:
        """Fetch complete tool data including manifest and code"""
        response = self._client.get(f"{self.master_url}/tools/get/{canonical_id}")

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()

        return ToolData(
            canonical_id=canonical_id,
            manifest=data.get("manifest", {}),
            code_python=data.get("code_python"),
            skills_md=data.get("skills_md"),
        )

    def get_skills(self, canonical_id: str) -> Optional[str]:
        """Fetch Skills.md content for a tool"""
        response = self._client.get(f"{self.master_url}/tools/get/{canonical_id}/skills")

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()
        return data.get("skills")

    def get_tool_with_skills(self, canonical_id: str) -> Optional[ToolData]:
        """Fetch tool with skills content included"""
        tool = self.get_tool(canonical_id)
        if tool:
            tool.skills_md = self.get_skills(canonical_id)
        return tool

    def register_endpoint(
        self,
        name: str,
        hostname: str,
        platform: str,
        mcp_bridge_version: str,
    ) -> Optional[dict]:
        """Register this MCP Bridge with Trust Anchor."""
        try:
            response = self._client.post(
                f"{self.master_url}/subscribers/register",
                json={
                    "hostname": hostname,
                    "platform": platform,
                    "version": mcp_bridge_version,
                },
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            return None
        except httpx.RequestError:
            return None

    def heartbeat(self, endpoint_id: str, tools_cached: int = 0) -> bool:
        """Send heartbeat to Trust Anchor."""
        if not endpoint_id or endpoint_id.startswith("unregistered"):
            return False

        try:
            response = self._client.post(
                f"{self.master_url}/subscribers/{endpoint_id}/heartbeat",
                json={"tool_count": tools_cached},
            )
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False
        except httpx.RequestError:
            return False

    def resolve_oid(self, oid: str) -> Optional[str]:
        """Resolve OID to canonical_id (if OID endpoint exists)."""
        try:
            response = self._client.get(f"{self.master_url}/oid/{oid}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data.get("canonical_id")
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None

    def list_runbooks(
        self,
        domain: Optional[str] = None,
        vendor: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[dict]:
        """List available runbooks with optional filters."""
        params = {}
        if domain:
            params["domain"] = domain
        if vendor:
            params["vendor"] = vendor
        if intent:
            params["intent"] = intent

        try:
            response = self._client.get(f"{self.master_url}/runbooks", params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json().get("runbooks", [])
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []

    def get_runbook_skills(self, runbook_id: str) -> Optional[str]:
        """Fetch Skills.md content for a runbook."""
        try:
            response = self._client.get(f"{self.master_url}/runbooks/get/{runbook_id}/skills")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json().get("skills")
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None

    def close(self):
        """Close the HTTP client"""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
