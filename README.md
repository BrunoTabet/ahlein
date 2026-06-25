# Clinic WhatsApp Bot

A multi-tenant AI bot that runs on a clinic's WhatsApp number. Patients message in Arabic
or English; the bot classifies the request against that clinic's service menu, finds a
slot, books it, answers basic FAQs, and hands off to a human for anything serious.

**One codebase, one app, many tenants.** A single webhook receives every clinic's
messages; the inbound `phone_number_id` resolves to a tenant, and everything downstream is
scoped to that tenant. Clinic content (services, doctors, hours, FAQ, credentials) lives in
the database — adding a clinic or swapping a doctor is a data edit, never a redeploy.

> **Status: Phase 1 (walking skeleton).** Single seeded clinic, end-to-end booking flow on
> the `mock` booking adapter, human-handoff path, simulator, and an eval suite. Later phases
> (real multi-tenancy + admin, RAG FAQ, reminders, more adapters) are outlined at the bottom.

## Architecture at a glance

```
WhatsApp Cloud API ─▶ POST /webhook ─▶ parse ─▶ resolve tenant (phone_number_id)
                                                      │
                                              TenantContext (config, menu, adapter)
                                                      │
                          Redis session + 24h window ◀┼▶ Claude tool-use loop
                                                      │     tools: select_service,
                                                      │            check_availability,
                                                      │            book_appointment,
                                                      │            handoff_to_human
                                                      ▼
                                          BookingAdapter (mock | calcom | …)
```

- **Knowledge as data.** One shared LLM (no per-clinic training). Each clinic's service
  menu + FAQ is injected into the system prompt at inference time. The model may only book
  services that exist in the menu.
- **Provider-swappable LLM.** The booking loop talks to an `LLMProvider` interface, so the
  model is a config choice (`LLM_PROVIDER=gemini|claude`) — Gemini is the default (native
  audio for the coming voice phase + strong Arabic + low cost); Claude is kept for the eval
  bake-off. History is stored in a neutral format, so you can switch providers freely.
- **Booking is adapter-bounded.** The bot calls `check_availability()` / `book_appointment()`
  only. `app/booking/calcom.py` is the first real adapter; an external-API or
  browser-automation adapter drops in beside it with no changes to bot logic.
- **Safety first.** No medical advice. A hard keyword screen (`app/safety/handoff.py`) hands
  off serious/sensitive complaints *before* the model runs; the model's `handoff_to_human`
  tool covers uncertainty and anything outside its flows.
- **Minimal patient data.** Only name, phone, chosen slot, and complaint *category* are
  persisted. Per-tenant credentials are Fernet-encrypted at rest.

| Area | Where |
|---|---|
| Webhook + payload parsing | `app/webhook/` |
| Tenant resolution / context | `app/tenancy/` |
| LLM loop, tools, prompt, providers | `app/llm/` (`providers/` = Gemini, Claude) |
| Booking adapters | `app/booking/` |
| Structured menu / FAQ render | `app/knowledge/` |
| Handoff rules | `app/safety/` |
| Redis session + 24h window | `app/conversation/` |
| Outbound WhatsApp send | `app/messaging/` |
| DB models + crypto | `app/db/` |

## Prerequisites

- Python 3.11–3.12 (some deps may not yet ship wheels for 3.13/3.14).
- Docker (for local Postgres + Redis), or your own Postgres-with-pgvector and Redis.
- An Anthropic API key (for the LLM loop and evals).

## Run locally

```bash
# 1. Infra
docker compose up -d

# 2. Environment
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   → paste into ENCRYPTION_KEY in .env, and set ANTHROPIC_API_KEY

# 3. Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 4. Schema + seed clinic
python -m scripts.init_db
python -m seeds.seed_tenant

# 5. Run
uvicorn app.main:app --reload
```

## Test the full flow with no real WhatsApp/phone

With the app running and the tenant seeded:

```bash
python -m scripts.simulate_message "can I book for my finger?"
# keep the same --from across calls to continue a conversation:
python -m scripts.simulate_message "tomorrow morning works"        --from 971500000001
python -m scripts.simulate_message "my name is Bruno Tabet"        --from 971500000001
python -m scripts.simulate_message "I think I might have cancer"   # → [HANDOFF]
python -m scripts.simulate_message "where do I park?"
```

The bot's reply is printed (and echoed in the webhook JSON response) so you never need a
real number in dev.

## Run the tests

```bash
pytest           # unit tests — no DB/Redis/API needed
```

## Quick LLM check (no Docker needed)

Verify the model wiring, tool-calling, and Arabic against a provider directly — needs only
the provider's API key, no DB/Redis:

```bash
python -m scripts.smoke_llm --provider gemini "can I book for my finger?"
python -m scripts.smoke_llm --provider gemini "أبغى موعد لإصبعي يوجعني"
python -m scripts.smoke_llm --provider claude "I might have a tumor"
```

## Run the evals

The LLM eval suite drives the same orchestrator path the webhook uses. Requires DB + Redis
+ `ANTHROPIC_API_KEY` (the cancer→handoff case runs offline). Seed the tenant first.

```bash
python -m evals.run_evals                 # uses LLM_PROVIDER from .env
python -m evals.run_evals --provider all  # bake-off: gemini vs claude, same cases
```

Covers: `my finger hurts` → orthopedics, `I have cancer` → handoff, `where do I park` → FAQ,
gibberish → clarify. Add cases in `evals/cases.yaml`. The `--provider all` bake-off is how
you choose the production model on data rather than vibes (especially once you add real
Gulf-Arabic cases).

## Deploy to Railway

1. Provision **PostgreSQL** and **Redis** add-ons; Railway injects `DATABASE_URL` /
   `REDIS_URL`. *(Use the `pgvector/pgvector` image or enable the `vector` extension.)*
2. Set env vars: `ENVIRONMENT=production`, `ANTHROPIC_API_KEY`, `ENCRYPTION_KEY`,
   `WHATSAPP_VERIFY_TOKEN`, and the model overrides if desired.
3. Deploy. `railway.json` starts uvicorn and health-checks `/health`. The `Procfile`
   `release` step runs `scripts.init_db`; run `python -m seeds.seed_tenant` once to load the
   demo clinic (replaced by the admin layer in Phase 2).
4. Point the Meta WhatsApp webhook at `https://<your-app>/webhook` using
   `WHATSAPP_VERIFY_TOKEN` for verification.

Keep a separate Railway environment (or project) for **staging** vs **production** — config
is fully env-driven via `ENVIRONMENT`.

## Configuration

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `local` / `staging` / `production` (gates real WhatsApp sends) |
| `DATABASE_URL` | Postgres (pgvector); `postgresql://` is auto-upgraded to asyncpg |
| `REDIS_URL` | Session + 24h-window state |
| `LLM_PROVIDER` | `gemini` (default) or `claude` |
| `GEMINI_API_KEY` | Google AI Studio key (`AIza...`) |
| `GEMINI_MODEL` | Default `gemini-3-flash-preview` |
| `ANTHROPIC_API_KEY` | Claude API key (only if using/comparing the Claude provider) |
| `CLASSIFIER_MODEL` | Claude model for the loop — default `claude-haiku-4-5` |
| `ESCALATION_MODEL` | `claude-sonnet-4-6` (reserved for ambiguous-turn escalation) |
| `ENCRYPTION_KEY` | Fernet key for encrypting tenant credentials |
| `WHATSAPP_VERIFY_TOKEN` | Meta webhook verification handshake |

## Roadmap (later phases — not built yet)

- **Phase 2** — real multi-tenancy in the DB + a simple admin layer (add clinic / edit
  doctors as data entry); Alembic migrations.
- **Phase 3** — RAG FAQ pipeline: doc upload → chunk → embed into pgvector → tenant-scoped
  retrieval (fills the `app/knowledge/rag.py` stub).
- **Phase 4** — reminders / no-show nudges via approved WhatsApp utility templates (uses the
  24h-window tracking already in place).
- **Phase 5** — additional booking adapters (external API, browser automation) beside the
  Cal.com adapter.

## Notes / Phase 1 simplifications

- Schema is bootstrapped via `create_all` + the pgvector extension; **Alembic** lands in
  Phase 2 where schema churn begins.
- The seeded clinic uses the `mock` booking adapter so the flow runs with no Cal.com
  account. The Cal.com v2 adapter (`app/booking/calcom.py`) is implemented against the live
  API shape — verify the `cal-api-version` constants against a real account before pointing
  a clinic at it.
- FAQs are inline per tenant (injected into the prompt). The scalable doc-embedding pipeline
  is Phase 3.
- Tenant config is loaded fresh from the DB on every message (no caching) so data edits take
  effect immediately; a short-lived cache is a Phase 2 optimization.
