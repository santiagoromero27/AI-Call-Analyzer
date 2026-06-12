from pydantic import BaseModel


class MojaWebhook(BaseModel):
    """Matches the JSON body configured in Moja's outgoing webhook form."""
    recording_url: str
    caller_id: str
    publisher_name: str
    buyer_name: str
    campaign_name: str = ""


class ChatRequest(BaseModel):
    message: str
