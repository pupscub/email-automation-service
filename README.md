## Email Automation Service

Monitors a Microsoft Outlook inbox in real time (push/webhooks) and automatically generates contextually appropriate draft replies using GPT-4. Runs locally; uses Microsoft Graph.

### Features
- Real-time inbox monitoring (Graph webhooks; no polling)
- AI-generated draft replies saved to Drafts
- History-aware: looks up recent emails by sender/subject (reliable for personal accounts)
- Simple UI with Start/Stop and a live “Recent AI-generated Drafts” panel
- Diagnostics: health and debug endpoints; structured logging

### Requirements
- Python 3.10+
- Microsoft Entra app registration (Azure AD)
- OpenAI API key
- ngrok (or similar) for webhook tunneling

### 1) Azure App Registration (Microsoft Graph)
1. Azure Portal → App registrations → New registration
   - Supported account types:
     - For Outlook.com (personal): Accounts in any org directory and personal Microsoft accounts; set `TENANT_ID=consumers`
     - For work/school: your tenant; set `TENANT_ID=<your-tenant-id>`
   - Redirect URI: `http://localhost:8000/auth/callback`
2. Grab `Application (client) ID` and `Directory (tenant) ID`
3. Certificates & secrets → New client secret → copy the value
4. API permissions (Delegated): `User.Read`, `Mail.Read`, `Mail.ReadWrite`, `Mail.Send` (grant admin consent if required)

### 2) Local setup (uv)
```bash
# ensure uv is installed: https://docs.astral.sh/uv/getting-started/installation/
uv sync                 # creates .venv and installs from pyproject.toml/uv.lock
cp .env.example .env    # then edit .env

# optional: activate the venv created by uv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Update `.env`:
```env
CLIENT_ID=...
CLIENT_SECRET=...
TENANT_ID=consumers              # or your tenant GUID
REDIRECT_URI=http://localhost:8000/auth/callback
OPENAI_API_KEY=...
# Either set WEBHOOK_URL here, or use /webhook/start_with_url at runtime
WEBHOOK_URL=
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

### 3) Run the app and tunnel
Terminal 1:
```bash
python main.py           # or: uv run python main.py
```
Terminal 2:
```bash
ngrok http 8000
```

### 4) Authenticate and start monitoring
Option A (UI):
1. Open `http://localhost:8000`
2. Sign in with Microsoft; consent the requested scopes
3. Click “Start Monitoring”

Option B (API with runtime URL):
```bash
curl -X POST http://localhost:8000/webhook/start_with_url \
  -H 'content-type: application/json' \
  -d '{"webhook_url":"https://<your-ngrok-https>"}'
```

You should see “Recent AI-generated Drafts” populate after you receive new emails.

### 5) Testing
- Local sanity checks:
```bash
python -m tests.test_local
```

- Validate ngrok (replace URL):
```bash
python -m tests.test_ngrok https://<your-ngrok-https>
```

- End-to-end (starts ngrok, starts monitoring, sends test mail, verifies draft):
```bash
python -m tests.test_e2e
```

### Test Output Screenshots
Add the screenshots under `docs/images/` with the following names to render them below.

1) Ngrok validation test

![Ngrok test](docs/images/test_ngrok.png)

2) End‑to‑end test (starts ngrok, starts monitoring, sends email, verifies draft)

![E2E test](docs/images/test_e2e.png)

3) Local endpoints test

![Local test](docs/images/test_local.png)

### Endpoints (high level)
- `GET /` UI; Start/Stop buttons and recent drafts panel
- `POST /webhook/start` start monitoring using `WEBHOOK_URL` from .env
- `POST /webhook/start_with_url` start with a provided tunnel URL
- `POST /webhook/stop` stop monitoring
- `GET|POST /webhook` Graph webhook endpoint (handles validation token and notifications)
- `GET /ui/recent-drafts` recent generated drafts for UI/testing
- `GET /health` service status
- Debug (optional): `/debug/me`, `/debug/me/mailfolders`, `/debug/me/messages`, `/debug/token`, `/debug/token/claims`, `/debug/me/messages/raw`, `/debug/send_test_email`

### How it works (brief)
1. User authenticates (MSAL); tokens cached locally
2. App creates a Graph subscription to Inbox; Graph validates the webhook URL
3. On new message notification, app fetches the email, builds a history context using `$filter` (reliable for personal accounts), generates an AI draft, and saves it via Graph `createReply`
4. Draft metadata is exposed to the UI via `/ui/recent-drafts`

### Tradeoffs and choices
- Webhooks over polling for scalability and responsiveness
- `$filter` (sender/date + client-side subject) for Outlook.com reliability; `$search` often 400s on personal accounts
- TTL dedup guard for duplicate notifications; can be upgraded to category-based idempotency
- GPT-5 for higher-quality drafts; simple prompt strategy for speed

### Roadmap
- Auto-renew and persist subscriptions
- Category-based idempotency and message tagging
- Richer similarity using embeddings
- Multi-tenant and role-based UI


### Project structure
```
email-automation/
├── src/
│   ├── config.py            # Env config
│   ├── auth.py              # MSAL auth
│   ├── graph_client.py      # Graph calls
│   ├── ai_service.py        # OpenAI reply generator
│   └── webhook_handler.py   # Webhook processing
├── tests/
│   ├── __init__.py
│   ├── test_local.py        # local endpoints
│   ├── test_ngrok.py        # ngrok reachability
│   └── test_e2e.py          # automated E2E
├── main.py                  # FastAPI app & routes
├── requirements.txt
├── setup.py                 # optional helper
├── .env.example
└── README.md
```
