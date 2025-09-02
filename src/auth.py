import json
import os
from typing import Optional, Dict, Any
import msal
from src.config import config
import logging

logger = logging.getLogger(__name__)

# store tokens for quick login
class MSALTokenCache:
    def __init__(self, cache_file: str = "token_cache.json"):
        self.cache_file = cache_file
        self.cache = msal.SerializableTokenCache()
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                self.cache.deserialize(f.read())
    
    def save(self):
        if self.cache.has_state_changed:
            with open(self.cache_file, 'w') as f:
                f.write(self.cache.serialize())

class GraphAuthenticator:
    def __init__(self):
        self.token_cache = MSALTokenCache()
        
        # Validate configuration
        if not config.client_id or not config.client_secret or not config.tenant_id:
            raise ValueError("Missing required OAuth configuration. Please check CLIENT_ID, CLIENT_SECRET, and TENANT_ID in .env file")
        
        self.app = msal.ConfidentialClientApplication(
            client_id=config.client_id,
            client_credential=config.client_secret,
            authority=f"https://login.microsoftonline.com/{config.tenant_id}",
            token_cache=self.token_cache.cache
        )
        # Use delegated permission scopes in short form per Microsoft identity platform guidance
        #NOTE: this could be saved in .env or other configurable file maybe?
        self.scopes = [
            "User.Read",
            "Mail.Read",
            "Mail.ReadWrite",
            "Mail.Send",
        ]
    
    def get_auth_url(self, claims: str | None = None) -> str:
        extra = {"prompt": "consent"}
        if claims:
            extra["claims"] = claims
        auth_url = self.app.get_authorization_request_url(
            scopes=self.scopes,
            redirect_uri=config.redirect_uri,
            **extra,
        )
        return auth_url
    
    #NOTE: can have pydantic module instead of Dict[str, any] --- out of scope
    def get_token_from_code(self, code: str, claims: str | None = None) -> Optional[Dict[str, Any]]:
        try:
            result = self.app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.scopes,
                redirect_uri=config.redirect_uri,
                claims_challenge=claims
            )
            
            if "access_token" in result:
                self.token_cache.save()
                logger.info("Successfully obtained access token")
                return result
            else:
                error = result.get("error", "Unknown error")
                error_description = result.get("error_description", "No description")
                logger.error(f"Token acquisition failed: {error} - {error_description}")
                return None
                
        except Exception as e:
            logger.exception(f"Exception during token acquisition: {str(e)}")
            return None
    
    def get_token_silent(self) -> Optional[str]:
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(
                scopes=self.scopes,
                account=accounts[0]
            )
            
            if "access_token" in result:
                self.token_cache.save()
                return result["access_token"]
        return None
    
    
    # App-only token is not used in current flow; remove to simplify public surface.
    
    def refresh_token(self) -> Optional[str]:
        return self.get_token_silent()

authenticator = GraphAuthenticator()