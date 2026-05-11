from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class SessionState(str, Enum):
    AWAITING_FILE = "awaiting_file"
    FILE_PARSED = "file_parsed"
    AWAITING_POOL_SELECTION = "awaiting_pool_selection"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    COMPLETE = "complete"
    ERROR = "error"


class CandidateRecord(BaseModel):
    row_number: int
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class ValidationError(BaseModel):
    row_number: int
    field: str
    reason: str


class ParseResult(BaseModel):
    valid_records: List[CandidateRecord]
    invalid_records: List[ValidationError]
    total_rows: int
    valid_count: int
    invalid_count: int


class CandidatePool(BaseModel):
    pool_id: str
    pool_name: str


class AgentSession(BaseModel):
    session_id: str
    recruiter_id: str
    state: SessionState = SessionState.AWAITING_FILE
    parse_result: Optional[ParseResult] = None
    selected_pool: Optional[CandidatePool] = None
    available_pools: List[CandidatePool] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UploadRequest(BaseModel):
    session_id: str
    recruiter_id: str
    file_content_base64: str
    filename: str


class MessageRequest(BaseModel):
    session_id: str
    recruiter_id: str
    message: str


class AgentResponse(BaseModel):
    session_id: str
    state: SessionState
    message: str
    available_pools: Optional[List[CandidatePool]] = None
    parse_result: Optional[ParseResult] = None
    success: bool = True


class AuditLogEntry(BaseModel):
    session_id: str
    recruiter_id: str
    pool_id: str
    pool_name: str
    records_submitted: int
    records_succeeded: int
    records_failed: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
