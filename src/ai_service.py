from typing import List, Dict, Any, Optional
import openai
from openai import OpenAI
from src.config import config
from src.prompts import (
    build_prompt_simple,
    build_prompt_with_similar,
    build_prompt_with_history,
    SYSTEM_PROMPT,
)

class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=config.openai_api_key)
    
    def extract_email_context(self, email: Dict[str, Any]) -> str:
        subject = email.get("subject", "")
        body = email.get("body", {}).get("content", "")
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
        
        if len(body) > 2000:
            body = body[:2000] + "..."
        
        return f"From: {sender}\nSubject: {subject}\nBody: {body}"
    
    def find_similar_email_responses(self, current_email: Dict[str, Any], email_history: List[Dict[str, Any]]):
        current_subject = current_email.get("subject", "").lower()
        current_body = current_email.get("body", {}).get("content", "").lower()
        current_sender = current_email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
        
        best_match = None
        best_score = 0
        
        for email in email_history:
            # do not filter by attachments; consider all for similarity
            email_subject = email.get("subject", "").lower()
            email_body = email.get("body", {}).get("content", "").lower()
            email_sender = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
            
            score = 0
            
            if current_sender == email_sender:
                score += 30
            
            subject_words = set(current_subject.split())
            email_subject_words = set(email_subject.split())
            subject_overlap = len(subject_words.intersection(email_subject_words))
            if subject_overlap > 0:
                score += subject_overlap * 10
            
            body_words = set(current_body.split()[:50])
            email_body_words = set(email_body.split()[:50])
            body_overlap = len(body_words.intersection(email_body_words))
            if body_overlap > 2:
                score += body_overlap * 5
            
            # light recency bonus if available
            rdt = email.get("receivedDateTime") or email.get("lastModifiedDateTime")
            if rdt:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.fromisoformat(rdt.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - dt).days
                    score += max(0, 20 - age_days)
                except Exception:
                    pass

            if score > best_score and score > 20:
                best_score = score
                best_match = email
        
        if best_match:
            return self.extract_email_context(best_match), best_match
        return (None, None)
    
    
    #NOTE: If an email goes in junk this does not work
    
    
    def generate_draft_reply(self, current_email: Dict[str, Any], similar_response: Optional[str] = None, history_context: Optional[str] = None) -> str:
        current_context = self.extract_email_context(current_email)
        
        if similar_response and history_context:
            prompt = build_prompt_with_history(current_context, similar_response, history_context)
        elif similar_response:
            prompt = build_prompt_with_similar(current_context, similar_response)
        else:
            prompt = build_prompt_simple(current_context)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            return f"Thank you for your email. I'll review this and get back to you shortly.\n\nBest regards"

ai_service = AIService()