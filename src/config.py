import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Config(BaseModel):
    client_id: str
    client_secret: str
    tenant_id: str
    redirect_uri: str
    openai_api_key: str
    webhook_url: str
    webhook_secret: str
    host: str = "localhost"
    port: int = 8000
    debug: bool = True
    
    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            client_id=os.getenv("CLIENT_ID", ""),
            client_secret=os.getenv("CLIENT_SECRET", ""),
            tenant_id=os.getenv("TENANT_ID", ""),
            redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            webhook_url=os.getenv("WEBHOOK_URL", ""),
            webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
            host=os.getenv("HOST", "localhost"),
            port=int(os.getenv("PORT", "8000")),
            debug=os.getenv("DEBUG", "true").lower() == "true"
        )

config = Config.from_env()