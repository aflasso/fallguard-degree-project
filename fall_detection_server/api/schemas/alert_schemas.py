"""
Schemas Pydantic para alertas.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FallAlertSchema(BaseModel):
    type:       str
    module_id:  str
    timestamp:  datetime
    confidence: float
    clip_id:    str
    clip_url:   str


class RequestUploadUrlSchema(BaseModel):
    type:      str = "request_upload_url"
    module_id: str
    clip_id:   str


class UpdateAlertStatusSchema(BaseModel):
    status: str


class AlertResponseSchema(BaseModel):
    alert_id:   str
    module_id:  str
    timestamp:  datetime
    confidence: float
    clip_url:   Optional[str] = None
    seen:       bool          = False
    status:     str           = "detected"