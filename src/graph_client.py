import json
from typing import Dict, List, Optional, Any
import requests
from datetime import datetime, timedelta, timezone
from src.auth import authenticator
import time
import asyncio
import aiohttp
import logging

logger = logging.getLogger(__name__)

class GraphClient:
    def __init__(self):
        self.base_url = "https://graph.microsoft.com/v1.0"
        """Thin wrapper around Microsoft Graph endpoints used by the app."""
        
    def _get_headers(self) -> Dict[str, str]:
        """Return default headers with delegated user token."""
        token = authenticator.get_token_silent()
        if not token:
            raise Exception("No valid access token available")
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_user_info(self) -> Dict[str, Any]:
        """Fetch current user's basic profile info."""
        response = requests.get(
            f"{self.base_url}/me",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()
    
    async def create_webhook_subscription(self, webhook_url: str) -> Dict[str, Any]:
        """Create a change notification subscription on the Inbox folder."""
        subscription_data = {
            "changeType": "created",
            "notificationUrl": webhook_url,
            # Target the Inbox explicitly; delegated permissions must include Mail.Read (or higher)
            "resource": "me/mailFolders('inbox')/messages",
            "expirationDateTime": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            # Remove clientState for now
        }
        
        try:
            logger.info(f"Creating webhook subscription to: {webhook_url}")
            logger.info(f"Subscription data: {subscription_data}")
            
            # Use regular delegated permissions headers
            headers = self._get_headers()  # Back to regular headers, not app-only
            
            # Use aiohttp for async request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/subscriptions",
                    headers=headers,
                    json=subscription_data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Webhook subscription created successfully: {result.get('id')}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Subscription creation failed with status {response.status}")
                        logger.error(f"Response Body: {error_text}")
                        raise Exception(f"Subscription creation failed: {error_text}")
                        
        except Exception as e:
            logger.exception(f"Exception creating webhook subscription: {str(e)}")
            raise
        
    
    
    def delete_webhook_subscription(self, subscription_id: str) -> bool:
        """Delete an existing subscription by id."""
        response = requests.delete(
            f"{self.base_url}/subscriptions/{subscription_id}",
            headers=self._get_headers()
        )
        return response.status_code == 204
    
    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Fetch a single message by id."""
        response = requests.get(
            f"{self.base_url}/me/messages/{message_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()
    
    def search_email_history(self, sender: Optional[str] = None, subject_contains: Optional[str] = None, days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
        """Use $filter over recent emails to approximate search.
        - Filters by receivedDateTime window
        - Optionally filters by sender and subject contains (case-insensitive)
        Works reliably for personal accounts.
        """
        filter_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        # Start with date filter
        filters = [f"receivedDateTime ge {filter_date}"]
        if sender:
            # Graph filter on from/emailAddress/address eq 'sender'
            filters.append(f"from/emailAddress/address eq '{sender}'")
        # Note: 'contains' is not supported in $filter for Graph messages; we'll filter client-side for subject
        params = {
            "$filter": " and ".join(filters),
            "$top": limit,
            "$orderby": "receivedDateTime desc"
        }
        response = requests.get(
            f"{self.base_url}/me/messages",
            headers=self._get_headers(),
            params=params
        )
        response.raise_for_status()
        items = response.json().get("value", [])
        # Client-side subject contains filter if requested
        if subject_contains:
            needle = subject_contains.lower()
            items = [m for m in items if needle in (m.get("subject", "").lower())]
        return items
    
    def get_recent_emails(self, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent emails by receivedDateTime window, newest first."""
        filter_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        params = {
            "$filter": f"receivedDateTime ge {filter_date}",
            "$top": limit,
            "$orderby": "receivedDateTime desc"
        }
        
        response = requests.get(
            f"{self.base_url}/me/messages",
            headers=self._get_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json().get("value", [])
    
    def get_messages_from_sender(self, sender_email: str, days: int = 365, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent messages from a specific sender.
        Uses $filter on from/emailAddress/address and a receivedDateTime window.
        """
        if not sender_email:
            return []
        filter_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        filters = [
            f"receivedDateTime ge {filter_date}",
            f"from/emailAddress/address eq '{sender_email}'"
        ]
        params = {
            "$filter": " and ".join(filters),
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "subject,bodyPreview,from,receivedDateTime,id"
        }
        response = requests.get(
            f"{self.base_url}/me/messages",
            headers=self._get_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json().get("value", [])

    def get_drafts_to_recipient(self, recipient_email: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch recent drafts and filter client-side by recipient address.
        Outlook.com often rejects toRecipients any() filters; this path remains reliable.
        """
        if not recipient_email:
            return []
        params = {
            "$filter": "isDraft eq true",
            "$top": max(limit, 25),
            "$orderby": "lastModifiedDateTime desc",
            "$select": "subject,bodyPreview,toRecipients,lastModifiedDateTime,id"
        }
        response = requests.get(
            f"{self.base_url}/me/messages",
            headers=self._get_headers(),
            params=params
        )
        response.raise_for_status()
        items = response.json().get("value", [])
        target = recipient_email.lower()
        filtered: List[Dict[str, Any]] = []
        for msg in items:
            recips = msg.get("toRecipients", []) or []
            for r in recips:
                addr = ((r or {}).get("emailAddress", {}) or {}).get("address", "")
                if addr and addr.lower() == target:
                    filtered.append(msg)
                    break
        return filtered[:limit]
    
    def create_draft_reply(self, original_message_id: str, reply_content: str) -> Dict[str, Any]:
        """Create a draft reply to the given message id with provided HTML content."""
        draft_data = {
            "message": {
                "body": {
                    "contentType": "HTML",
                    "content": reply_content
                }
            }
        }
        
        response = requests.post(
            f"{self.base_url}/me/messages/{original_message_id}/createReply",
            headers=self._get_headers(),
            json=draft_data
        )
        response.raise_for_status()
        return response.json()

    def send_mail(self, to_address: str, subject: str, body_html: str) -> None:
        """Send an email using the signed-in user's mailbox."""
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": [
                    {"emailAddress": {"address": to_address}}
                ],
            },
            "saveToSentItems": True,
        }
        response = requests.post(
            f"{self.base_url}/me/sendMail",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()

graph_client = GraphClient()