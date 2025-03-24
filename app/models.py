from pydantic import BaseModel
from datetime import datetime
from typing import Optional

file_status_db = {}

class FileStatus(BaseModel):
    file_id: str
    last_updated: datetime
    received_end_byte: int
    status: str  # "partial", "complete", or "stale_saved"

class UploadChunkRequest(BaseModel):
    file_id: str
    start_byte: int
    end_byte: int
    checksum: int

class FileStatusResponse(BaseModel):
    file_id: str
    status: str
    received_bytes: int
    expected_next_byte: int
    completed: bool

class TokenRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
