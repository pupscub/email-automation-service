from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, List, Dict, Any


class SendTestEmailRequest(BaseModel):
    subject: str
    body: str


class StartWithUrlRequest(BaseModel):
    webhook_url: HttpUrl


class RecentDraft(BaseModel):
    message_id: str
    sender: str
    subject: str
    draft_preview: str
    created_at: str
    similar_sender: Optional[str] = None
    similar_subject: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None

