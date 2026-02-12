"""
Publisher Node Models

Pydantic models for Publisher Node request/response validation.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ToolStatus(str, Enum):
    """Status of a tool in the certification pipeline."""
    PENDING = "pending"
    CERTIFIED = "certified"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


# =============================================================================
# REQUEST MODELS
# =============================================================================

class ToolSubmission(BaseModel):
    """Request body for POST /publisher/submit-tool."""
    manifest: Dict[str, Any] = Field(
        ...,
        description="Tool manifest containing metadata, parameters, capabilities"
    )
    code_python: str = Field(
        ...,
        min_length=10,
        description="Python source code with main(context) function"
    )
    skills_md: Optional[str] = Field(
        default=None,
        description="Skills.md content for AI guidance"
    )

    @field_validator("manifest")
    @classmethod
    def validate_manifest(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate manifest has required fields."""
        required = ["canonical_id", "name", "version"]
        for field in required:
            if field not in v:
                raise ValueError(f"manifest.{field} is required")
        return v

    @field_validator("code_python")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate Python code has main function."""
        if "def main(" not in v:
            raise ValueError("Python code must contain 'def main(context)' function")
        return v


class CertifyRequest(BaseModel):
    """Request body for POST /publisher/certify/{id}."""
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional certification notes"
    )


class RejectRequest(BaseModel):
    """Request body for POST /publisher/reject/{id}."""
    reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Reason for rejection"
    )


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class ToolSubmissionResponse(BaseModel):
    """Response for POST /publisher/submit-tool."""
    canonical_id: str
    status: ToolStatus = ToolStatus.PENDING
    code_hash: str
    signed_at: datetime
    key_id: str


class ToolDetailResponse(BaseModel):
    """Response for GET /publisher/tool/{id}."""
    canonical_id: str
    manifest: Dict[str, Any]
    status: ToolStatus
    code_hash: str
    signed_at: datetime
    key_id: str
    submitted_at: datetime
    certified_at: Optional[datetime] = None
    certified_by: Optional[str] = None


class ToolListItem(BaseModel):
    """Item in tool list responses."""
    canonical_id: str
    name: str
    status: ToolStatus
    submitted_at: datetime
    certified_at: Optional[datetime] = None


class ToolListResponse(BaseModel):
    """Response for GET /publisher/my-tools."""
    tools: List[ToolListItem]
    total: int
    limit: int = 50
    offset: int = 0


class PendingToolsResponse(BaseModel):
    """Response for GET /publisher/pending."""
    tools: List[ToolListItem]
    count: int


class CertifyResponse(BaseModel):
    """Response for POST /publisher/certify/{id}."""
    canonical_id: str
    status: ToolStatus = ToolStatus.CERTIFIED
    certified_at: datetime
    certified_by: str


class RejectResponse(BaseModel):
    """Response for POST /publisher/reject/{id}."""
    canonical_id: str
    status: ToolStatus = ToolStatus.REJECTED
    rejected_at: datetime
    reason: str


class HealthResponse(BaseModel):
    """Response for GET /publisher/health."""
    status: str = "healthy"
    timestamp: datetime
    keys_loaded: bool
    key_version: str


# =============================================================================
# INTERNAL MODELS
# =============================================================================

class SigningPayload(BaseModel):
    """Internal model for the data that gets signed."""
    canonical_id: str
    version: str
    code_hash_sha256: str
    signed_at: datetime
    key_id: str

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Convert to dict for canonicalization."""
        return {
            "canonical_id": self.canonical_id,
            "version": self.version,
            "code_hash_sha256": self.code_hash_sha256,
            "signed_at": self.signed_at.isoformat() + "Z",
            "key_id": self.key_id,
        }
