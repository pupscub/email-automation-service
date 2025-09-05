import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
import json

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from src.deps import (
    get_config,
    get_authenticator,
    get_graph_client,
    get_webhook_handler,
)
from src.config import config
from src.auth import GraphAuthenticator
from src.graph_client import GraphClient
from src.webhook_handler import WebhookHandler
from src.models.schemas import SendTestEmailRequest, StartWithUrlRequest, RecentDraft
from src.graph_client import graph_client as _graph_client_singleton

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

subscription_id = None
claims_challenge = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting email automation service...")
    yield
    
    global subscription_id
    if subscription_id:
        try:
            # Use singleton here since Depends is not available in lifespan
            _graph_client_singleton.delete_webhook_subscription(subscription_id)
            logger.info("Deleted webhook subscription")
        except Exception as e:
            logger.error(f"Error deleting subscription: {e}")

app = FastAPI(
    title="Email Automation Service",
    description="Automated email draft generation with Microsoft Graph API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def root(authenticator: GraphAuthenticator = Depends(get_authenticator),
               graph_client: GraphClient = Depends(get_graph_client)):
    token = authenticator.get_token_silent()
    if token:
        user_info = graph_client.get_user_info()
        user_name = user_info.get("displayName", "Unknown User")
        user_email = user_info.get("mail") or user_info.get("userPrincipalName", "")
        
        status = "✅ Connected" if subscription_id else "⚠️ Not monitoring"
        
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 1000px; margin: 30px auto; padding: 20px;">
                <h1>📧 Email Automation Service</h1>
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h2>Account Status</h2>
                    <p><strong>User:</strong> {user_name}</p>
                    <p><strong>Email:</strong> {user_email}</p>
                    <p><strong>Monitoring:</strong> {status}</p>
                </div>
                
                <div style="margin: 20px 0;">
                    <button onclick="startMonitoring()" style="background-color: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px;">
                        Start Monitoring
                    </button>
                    <button onclick="stopMonitoring()" style="background-color: #dc3545; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">
                        Stop Monitoring
                    </button>
                </div>
                <div style="background-color: #fdfdfd; padding: 15px; border-radius: 8px; border: 1px solid #eee;">
                    <h3>Recent AI-generated Drafts</h3>
                    <div id="drafts"></div>
                </div>
                
                <div style="background-color: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3>How it works:</h3>
                    <ol>
                        <li>Service monitors your Outlook inbox in real-time</li>
                        <li>When new emails arrive, it searches your email history for similar messages</li>
                        <li>AI generates contextually appropriate draft replies</li>
                        <li>Drafts are saved to your Outlook Drafts folder</li>
                    </ol>
                </div>
                
                <script>
                    async function startMonitoring() {{
                        const response = await fetch('/webhook/start', {{method: 'POST'}});
                        const result = await response.text();
                        alert(result);
                        location.reload();
                    }}
                    
                    async function stopMonitoring() {{
                        const response = await fetch('/webhook/stop', {{method: 'POST'}});
                        const result = await response.text();
                        alert(result);
                        location.reload();
                    }}
                    async function loadDrafts() {{
                        const resp = await fetch('/ui/recent-drafts');
                        const data = await resp.json();
                        const container = document.getElementById('drafts');
                        if (!data || !Array.isArray(data.items) || data.items.length === 0) {{
                            container.innerHTML = '<p>No drafts yet.</p>';
                            return;
                        }}
                        const html = data.items.map(i => `
                            <div style=\"padding:12px; border: 1px solid #eee; border-radius:6px; margin-bottom:12px; background:#fff;\">
                                <div style=\"display:flex; gap:16px; flex-wrap:wrap;\">
                                    <div><strong>From:</strong> ${{i.sender}}</div>
                                    <div><strong>Subject:</strong> ${{i.subject}}</div>
                                    ${'${i.similar_subject ? `<div><strong>Similar From:</strong> ' + '${i.similar_sender}' + '</div><div><strong>Similar Subject:</strong> ' + '${i.similar_subject}' + '</div>` : ``}'}
                                    <div style=\"color:#888; font-size:12px; margin-left:auto;\">${{i.created_at}}</div>
                                </div>
                                <details style=\"margin-top:8px;\">
                                  <summary style=\"cursor:pointer;\"><strong>View Draft</strong></summary>
                                  <div style=\"padding:8px 0; white-space:pre-wrap;\">${{i.draft_preview}}</div>
                                </details>
                                ${'${(i.citations && i.citations.length) ? `<div style=\\"margin-top:8px;\\"><strong>Citations:</strong><ul style=\\"margin:4px 0;\\">` + i.citations.map(c => `<li>${c.subject || "(no subject)"} — ${c.date || ""}</li>`).join("") + `</ul></div>` : ``}'}
                            </div>
                        `).join('');
                        container.innerHTML = html;
                    }}
                    loadDrafts();
                </script>
            </body>
        </html>
        """
    else:
        auth_url = authenticator.get_auth_url(claims=claims_challenge)
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 100px auto; text-align: center;">
                <h1>📧 Email Automation Service</h1>
                <p>Please authenticate with Microsoft to continue</p>
                <a href="{auth_url}" style="background-color: #0078d4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    Sign in with Microsoft
                </a>
            </body>
        </html>
        """

@app.get("/auth/callback")
async def auth_callback(request: Request, authenticator: GraphAuthenticator = Depends(get_authenticator)):
    global claims_challenge
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    
    token_result = authenticator.get_token_from_code(code, claims=claims_challenge)
    if not token_result:
        raise HTTPException(status_code=400, detail="Failed to obtain access token")
    
    # Clear stored claims challenge after success
    claims_challenge = None
    return RedirectResponse(url="/", status_code=302)


# Legacy webhook handler code removed

@app.get("/webhook")
@app.post("/webhook")
async def webhook_endpoint(request: Request, handler: WebhookHandler = Depends(get_webhook_handler)):
    # Check for validation token in query parameters first
    validation_token = request.query_params.get("validationToken")
    
    if validation_token:
        logger.info(f"🔍 Microsoft Graph validation token received: {validation_token}")
        return PlainTextResponse(
            content=validation_token,
            status_code=200,
            headers={"Content-Type": "text/plain; charset=utf-8"}
        )
    
    # For POST requests without validation token in query params
    if request.method == "POST":
        try:
            body = await request.body()
            if body:
                try:
                    notification_data = json.loads(body)
                    result = await handler.handle_webhook_notification(notification_data)
                    return result
                except json.JSONDecodeError:
                    # If it's not JSON, might be validation data
                    pass
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # GET request without validation token
    return {"status": "webhook endpoint active"}

# Legacy start-monitoring code removed



# In main.py, make the endpoint async
@app.post("/webhook/start")
async def start_webhook_monitoring(authenticator: GraphAuthenticator = Depends(get_authenticator),
                                   graph_client: GraphClient = Depends(get_graph_client)):
    global subscription_id
    
    if subscription_id:
        return "Monitoring is already active"
    
    try:
        # Validate the signed-in account has a mailbox in its home tenant
        user_info = graph_client.get_user_info()
        upn = user_info.get("userPrincipalName", "") or ""
        mail = user_info.get("mail")
        if (not mail) or ("#EXT#" in upn):
            return (
                "Error: The signed-in account appears to be a guest or has no mailbox in this tenant. "
                "Sign in with a work/school account that has an Exchange Online mailbox in its home tenant, "
                "or configure TENANT_ID=consumers in your .env and ensure the app supports personal Microsoft accounts."
            )

        webhook_endpoint = f"{config.webhook_url}/webhook"
        logger.info(f"Creating webhook subscription to: {webhook_endpoint}")
        
        # Make this async so FastAPI can handle validation request
        subscription = await graph_client.create_webhook_subscription(webhook_endpoint)
        subscription_id = subscription.get("id")
        
        logger.info(f"Created webhook subscription: {subscription_id}")
        return f"Started monitoring inbox. Subscription ID: {subscription_id}"
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {str(e)}")
        return f"Error starting monitoring: {str(e)}"

@app.post("/webhook/start_with_url")
async def start_webhook_with_url(payload: StartWithUrlRequest,
                                 graph_client: GraphClient = Depends(get_graph_client)):
    """Start monitoring with a provided webhook base URL at runtime.
    Body: { "webhook_url": "https://....ngrok-free.app" }
    """
    global subscription_id
    if subscription_id:
        return "Monitoring is already active"
    base_url = str(payload.webhook_url)
    try:
        webhook_endpoint = f"{base_url.rstrip('/')}/webhook"
        logger.info(f"Creating webhook subscription to: {webhook_endpoint}")
        subscription = await graph_client.create_webhook_subscription(webhook_endpoint)
        subscription_id = subscription.get("id")
        logger.info(f"Created webhook subscription: {subscription_id}")
        return f"Started monitoring inbox. Subscription ID: {subscription_id}"
    except Exception as e:
        logger.error(f"Error starting monitoring: {str(e)}")
        return f"Error starting monitoring: {str(e)}"

@app.post("/debug/send_test_email")
async def send_test_email(payload: SendTestEmailRequest,
                          graph_client: GraphClient = Depends(get_graph_client)):
    """Send a test email to the signed-in user for E2E checks.
    Body: { "subject": "...", "body": "<p>...</p>" }
    """
    user = graph_client.get_user_info()
    to_addr = user.get("mail") or user.get("userPrincipalName")
    subject = payload.subject or "Test email from E2E script"
    body = payload.body or "<p>Hello from E2E</p>"
    graph_client.send_mail(to_addr, subject, body)
    return {"ok": True}

@app.post("/webhook/stop")
async def stop_webhook_monitoring(graph_client: GraphClient = Depends(get_graph_client)):
    global subscription_id
    
    if not subscription_id:
        return "Monitoring is not active"
    
    try:
        success = graph_client.delete_webhook_subscription(subscription_id)
        if success:
            logger.info(f"Deleted webhook subscription: {subscription_id}")
            subscription_id = None
            return "Stopped monitoring inbox"
        else:
            return "Failed to stop monitoring"
            
    except Exception as e:
        logger.error(f"Error stopping monitoring: {str(e)}")
        return f"Error stopping monitoring: {str(e)}"

@app.get("/health")
async def health_check(authenticator: GraphAuthenticator = Depends(get_authenticator)):
    token = authenticator.get_token_silent()
    return {
        "status": "healthy",
        "authenticated": token is not None,
        "monitoring": subscription_id is not None
    }

@app.get("/ui/recent-drafts")
async def recent_drafts(handler: WebhookHandler = Depends(get_webhook_handler)):
    # Provide recent drafts recorded by the webhook handler for UI display
    items = list(handler.recent_drafts) if hasattr(handler, 'recent_drafts') else []
    # Validation into Pydantic models (best-effort)
    safe_items = []
    for it in items:
        try:
            safe_items.append(RecentDraft(**it).dict())
        except Exception:
            safe_items.append(it)
    return {"items": safe_items}

@app.get("/debug/me/messages")
async def debug_list_messages(graph_client: GraphClient = Depends(get_graph_client)):
    try:
        # Try to list a few recent messages to validate token permissions
        emails = graph_client.get_recent_emails(days=7, limit=5)
        return {"ok": True, "count": len(emails)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/token")
async def debug_token(authenticator: GraphAuthenticator = Depends(get_authenticator)):
    try:
        token = authenticator.get_token_silent()
        if not token:
            raise HTTPException(status_code=401, detail="No token")
        # Only decode header for quick visibility; avoid printing full token
        return {"ok": True, "note": "Token acquired. Check scp claim via jwt.ms if needed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/token/claims")
async def debug_token_claims(authenticator: GraphAuthenticator = Depends(get_authenticator)):
    import base64
    import json as _json
    try:
        token = authenticator.get_token_silent()
        if not token:
            raise HTTPException(status_code=401, detail="No token")
        parts = token.split(".")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid token format")
        payload_b64 = parts[1]
        # Add padding for base64url decoding
        padding = '=' * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(payload_b64 + padding)
        claims = _json.loads(payload)
        # Return only relevant claims
        filtered = {k: claims.get(k) for k in ["aud", "iss", "tid", "scp", "roles", "appid", "upn", "preferred_username"] if k in claims}
        return {"ok": True, "claims": filtered}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/me/messages/raw")
async def debug_messages_raw(authenticator: GraphAuthenticator = Depends(get_authenticator)):
    import requests as _requests
    global claims_challenge
    try:
        token = authenticator.get_token_silent()
        if not token:
            raise HTTPException(status_code=401, detail="No token")
        headers = {"Authorization": f"Bearer {token}"}
        # Use a lightweight call
        resp = _requests.get("https://graph.microsoft.com/v1.0/me/messages?$top=1", headers=headers)
        result = {
            "status": resp.status_code,
            "www_authenticate": resp.headers.get("WWW-Authenticate"),
            "request_id": resp.headers.get("request-id"),
            "client_request_id": resp.headers.get("client-request-id"),
            "body": resp.text[:2000],
        }
        # Capture claims challenge if present
        wa = resp.headers.get("WWW-Authenticate", "")
        if resp.status_code == 401 and "claims=" in wa:
            import re
            m = re.search(r'claims="([^"]+)"', wa)
            if m:
                claims_challenge = m.group(1)
                result["captured_claims_challenge"] = True
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/retrieval")
async def debug_retrieval(q: str = "test", sender: str | None = None):
    try:
        from src.retrieval import retrieve_citations
        terms = [w for w in q.split() if len(w) > 2][:6]
        items = retrieve_citations(terms, sender=sender, top_k=5)
        return {"ok": True, "count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/debug/me")
async def debug_me(graph_client: GraphClient = Depends(get_graph_client)):
    try:
        info = graph_client.get_user_info()
        return {"ok": True, "user": {k: info.get(k) for k in ["id", "userPrincipalName", "mail", "displayName"]}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/me/mailfolders")
async def debug_mail_folders(authenticator: GraphAuthenticator = Depends(get_authenticator)):
    import requests as _requests
    try:
        token = authenticator.get_token_silent()
        if not token:
            raise HTTPException(status_code=401, detail="No token")
        headers = {"Authorization": f"Bearer {token}"}
        resp = _requests.get("https://graph.microsoft.com/v1.0/me/mailFolders?$top=5", headers=headers)
        return {
            "status": resp.status_code,
            "body": resp.text[:2000]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info"
    )