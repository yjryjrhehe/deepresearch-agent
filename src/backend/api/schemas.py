from pydantic import BaseModel
from typing import Optional

class ResearchRequest(BaseModel):
    goal: str
    thread_id: str

class ReviewRequest(BaseModel):
    thread_id: str
    action: str
    feedback: Optional[str] = None