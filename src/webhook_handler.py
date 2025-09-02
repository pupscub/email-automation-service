import hashlib
import hmac
import json
from typing import Dict, Any
from collections import deque
from datetime import datetime, timezone
import re
from fastapi import HTTPException
from src.config import config
from src.graph_client import graph_client
from src.ai_service import ai_service
import asyncio
import logging

logger = logging.getLogger(__name__)

class WebhookHandler:
    def __init__(self):
        self.processing_emails = set()
        self.last_notification = None
        # Keep recent processed items for UI (sender, subject, draft preview)
        self.recent_drafts = deque(maxlen=50)
        # Dedup map: message_id -> last processed timestamp
        self.recently_processed = {}
    
    def validate_webhook_signature(self, body: bytes, signature: str) -> bool:
        if not config.webhook_secret:
            return True
        
        expected_signature = hmac.new(
            config.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def handle_webhook_notification(self, notification_data: Dict[str, Any]) -> Dict[str, str]:
        try:
            logger.info(f"Received webhook payload: {notification_data}")
            self.last_notification = notification_data
            if notification_data.get("value"):
                for notification in notification_data["value"]:
                    await self._process_notification(notification)
            
            return {"status": "processed"}
        
        except Exception as e:
            logger.error(f"Error processing webhook notification: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _process_notification(self, notification: Dict[str, Any]):
        try:
            change_type = notification.get("changeType")
            resource_id = notification.get("resourceData", {}).get("id")
            if not resource_id:
                resource = notification.get("resource", "")
                # Try to extract message id from resource path: me/mailFolders('inbox')/messages('<id>')
                try:
                    import re
                    m = re.search(r"messages\('([^']+)'\)", resource)
                    if m:
                        resource_id = m.group(1)
                except Exception:
                    pass
            
            if change_type != "created" or not resource_id:
                logger.info(f"Skipping notification. changeType={change_type}, resource_id_present={bool(resource_id)}")
                return
            
            if resource_id in self.processing_emails:
                return
            # Dedup within short window (e.g., 60 seconds)
            #NOTE: this dedup cache is implemented because our webhook handler is not idempotent 
            
            import time as _time
            now = _time.time()
            last = self.recently_processed.get(resource_id)
            if last and now - last < 60:
                logger.info(f"Skipping duplicate notification for {resource_id}")
                return
            
            self.processing_emails.add(resource_id)
            
            try:
                await self._generate_draft_reply(resource_id)
            finally:
                self.processing_emails.discard(resource_id)
                self.recently_processed[resource_id] = now
                
        except Exception as e:
            logger.error(f"Error processing notification: {str(e)}")
            self.processing_emails.discard(resource_id)
    
    async def _generate_draft_reply(self, message_id: str):
        try:
            message = graph_client.get_message(message_id)
            
            if self._should_skip_email(message):
                logger.info(f"Skipping email {message_id} - auto-generated or from self")
                return
            
            sender_email = message.get("from", {}).get("emailAddress", {}).get("address", "")
            subject = message.get("subject", "")
            body_content = message.get("body", {}).get("content", "")
            
            # Prior context: emails from sender + drafts to that sender
            prior_from_sender = graph_client.get_messages_from_sender(sender_email, days=365, limit=50)
            drafts_to_sender = graph_client.get_drafts_to_recipient(sender_email, limit=25)
            email_history = prior_from_sender + drafts_to_sender

            similar_context, similar_email = ai_service.find_similar_email_responses(message, email_history)

            # Build compact history context for the agent
            def summarize(items):
                lines = []
                for it in items[:10]:
                    subj = it.get("subject", "")
                    prev = it.get("bodyPreview", "") or it.get("body", {}).get("content", "")
                    lines.append(f"Subject: {subj}\nPreview: {prev[:200]}")
                return "\n\n".join(lines)

            history_context = summarize(prior_from_sender) + ("\n\n--- Drafts ---\n" + summarize(drafts_to_sender) if drafts_to_sender else "")

            draft_content = ai_service.generate_draft_reply(message, similar_context, history_context)
            
            formatted_draft = self._format_draft_content(draft_content)
            
            draft = graph_client.create_draft_reply(message_id, formatted_draft)
            
            logger.info(f"Created draft reply for email {message_id}")
            # Record for UI display
            try:
                sender_display = message.get("from", {}).get("emailAddress", {}).get("address", "")
                draft_text_preview = re.sub(r'<[^>]+>', ' ', formatted_draft).strip()
                draft_text_preview = (draft_text_preview[:280] + "…") if len(draft_text_preview) > 280 else draft_text_preview
                self.recent_drafts.appendleft({
                    "message_id": message_id,
                    "sender": sender_display,
                    "subject": subject or "",
                    "draft_preview": draft_text_preview,
                    "similar_sender": (similar_email or {}).get("from", {}).get("emailAddress", {}).get("address", "") if similar_email else "",
                    "similar_subject": (similar_email or {}).get("subject", "") if similar_email else "",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                # Non-fatal if we fail to record preview
                pass
            
        except Exception as e:
            logger.error(f"Error generating draft reply for {message_id}: {str(e)}")
    
    def _should_skip_email(self, message: Dict[str, Any]) -> bool:
        categories = message.get("categories", [])
        if any("auto" in cat.lower() or "notification" in cat.lower() for cat in categories):
            return True
        
        subject = message.get("subject", "").lower()
        skip_subjects = ["out of office", "automatic reply", "delivery failure", "undeliverable"]
        if any(skip_term in subject for skip_term in skip_subjects):
            return True
        
        return False
    
    def _extract_search_terms(self, subject: str, body: str, sender: str) -> list:
        terms = []
        
        terms.append(sender.split('@')[0] if '@' in sender else sender)
        
        subject_words = [word for word in subject.split() if len(word) > 3]
        terms.extend(subject_words[:5])
        
        # Strip HTML tags to avoid terms like <meta>
        if '<' in body and '>' in body:
            body = re.sub(r'<[^>]+>', ' ', body)
        body_words = [word for word in body.split()[:100] if len(word) > 4 and '<' not in word and '>' not in word]
        terms.extend(body_words[:10])
        
        return list(set(terms))
    
    def _format_draft_content(self, content: str) -> str:
        if not content.startswith("<"):
            content = f"<div>{content}</div>"
        
        return content.replace('\n', '<br>')

webhook_handler = WebhookHandler()