# Email Automation Service — Technical Report

## Summary
A local FastAPI application that monitors an Outlook mailbox via Microsoft Graph webhooks, searches prior context, and generates high‑quality AI draft replies. Optimized for Outlook.com (consumers) and compatible with work/school tenants with small tweaks.

- Development time: ~3 hours
- AI tooling: Built in Cursor with GPT‑5 assistance for rapid prototyping, code edits, and reasoning

## Architecture
- Authentication: MSAL delegated flow; token cache (`token_cache.json`); silent refresh.
- Webhooks: Single endpoint `/webhook` handles both Graph validation and notifications; subscription targets `me/mailFolders('inbox')/messages`.
- Processing pipeline:
  1) Fetch new message by `message_id`.
  2) Gather history context: prior messages from the same sender AND your drafts to that sender.
  3) Choose the best similar prior email (sender equality, subject/body overlap, recency bonus).
  4) Build prompts (`src/prompts.py`) and generate a reply with OpenAI.
  5) Save the reply as a Draft via Graph `createReply`.
  6) Record metadata for UI display (`/ui/recent-drafts`).
- UI: Start/Stop controls; recent drafts with Similar From/Subject and an expandable “View Draft” section.
- Tests: `tests/test_local.py`, `tests/test_ngrok.py`, `tests/test_e2e.py` (starts ngrok, starts monitoring, sends a mail, verifies a draft via the UI API).

## End‑to‑End Flow
1. User authenticates (MSAL). Tokens are cached; future requests use silent refresh.
2. User starts monitoring → app creates a Graph subscription; Graph validates by calling `/webhook?validationToken=...` which we echo.
3. On each “created” message notification:
   - Dedup guard (in‑flight + TTL) prevents duplicates.
   - Fetch the message → assemble per‑sender context (prior messages + your drafts to that sender).
   - Select the best similar prior email; build a prompt using `src/prompts.py`.
   - Generate draft → save with `createReply` → publish an entry for the UI.
4. User can stop monitoring to delete the subscription.

## Design Choices (and Why)
- Webhooks over polling: Lower latency, scalable, aligns with Graph best practices.
- Outlook.com reliability (consumers):
  - Avoid `$search` (frequent 400s). Use `$filter` by date/sender + client‑side subject/body checks; add recency bonus.
  - Drafts filtering: folder‑scoped `toRecipients any()` can return 400; we fetch `isDraft eq true` from `/me/messages` and filter by recipient client‑side.
- Similarity strategy: Focus on the same sender; combine subject/body word overlap and recency. This gives reliable retrieval without complex indexing.
- Prompt isolation: `src/prompts.py` holds all prompt templates, so tone/strategy can be tuned without touching logic.
- Idempotency: 2‑layer guard to handle at‑least‑once delivery.

## Technical Challenges and Solutions
- Subscription 401s
  - Causes: scope format, guest/no mailbox, Conditional Access claims challenges.
  - Fixes: use short‑form delegated scopes; detect guest/no‑mailbox; capture/round‑trip claims challenge; add diagnostics endpoints.

- Webhook URL reachability
  - Cause: ephemeral/unresolvable tunnels (e.g., some trycloudflare URLs) not reachable from Graph.
  - Fix: standardize on ngrok; add `/webhook/start_with_url` to pass the runtime URL.

- `$search` 400s on Outlook.com
  - Cause: AQS not supported/reliable; punctuation/entities break queries.
  - Fix: `$filter` by date/sender + client‑side subject/body matching with recency bonus.

- Drafts recipient filtering 400
  - Cause: `toRecipients any()` + Drafts folder path is rejected on Outlook.com.
  - Fix: query `/me/messages?$filter=isDraft eq true` and filter recipients client‑side.

- Idempotency (duplicate drafts)
  - Problem: Graph may redeliver notifications; handler initially created multiple drafts.
  - Solution: In `src/webhook_handler.py`:
    - `processing_emails` set blocks concurrent re‑entry for the same `message_id`.
    - `recently_processed[message_id]` TTL (60s) skips near‑duplicate notifications.

## Accuracy Strategy
- Gather rich per‑sender context:
  - Prior emails from the same sender.
  - Your drafts addressed to that sender.
- Select best similar prior item by sender equality, subject/body overlap, and recency.
- Prompt the model with:
  - Current email context
  - Best similar email context
  - Compact summaries of prior same‑sender messages and drafts
- Outcome: Drafts remain consistent with how you answered this sender before, but adapt to the current message.

## Testing and Diagnostics
- `tests/test_local.py` – basic endpoint checks.
- `tests/test_ngrok.py` – ngrok reachability and validation echo.
- `tests/test_e2e.py` – starts ngrok, starts monitoring, sends mail, polls `/ui/recent-drafts` for a draft.
- Debug endpoints: token/claims, Graph reachability, raw headers (claims challenges), and a test email sender.

## Limitations
- No subscription auto‑renew/persistence (explicitly allowed by spec).
- Idempotency cache is in‑memory; not persisted across restarts.
- Similarity is lexical + recency; no embeddings yet.
- Inbox only (monitoring other folders optional).

## Next Steps
1. Idempotency hardening: message category/tag after drafting; check existing drafts; persist processed IDs.
2. Subscription lifecycle: persist subscription ID and auto‑renew around 60–65 minutes.
3. Better similarity: add embeddings (e.g., text‑embedding‑3‑small), thread‑aware context retrieval.
4. Coverage & UX: toggle “monitor all folders”; full message view; show full matched email; approve & send.
5. Observability: structured file/JSON logs with Graph request‑ids; metrics; retries/backoff for transient errors.
6. Multi‑tenant hardening for production: RBAC, secure secret management, CI.

## Key Files
- `main.py` – FastAPI app and routes
- `src/auth.py` – MSAL auth and token cache
- `src/graph_client.py` – Graph helpers (subscribe, read, draft, send)
- `src/webhook_handler.py` – webhook processing, dedup, context assembly
- `src/ai_service.py` – similarity and draft generation
- `src/prompts.py` – prompt templates
- `tests/` – local, ngrok, and E2E tests
