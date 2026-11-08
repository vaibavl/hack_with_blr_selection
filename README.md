# 🏦 BharatApex AI — ClientCare Conversational Banking Agent

> A full-stack **FinTech customer-support AI agent** for an Indian commercial bank ("BharatApex"),
> with **persistent long-term client memory**, tool-calling over a synthetic core-banking layer,
> and a compliance guardrail engine (RBI / NPCI / FEMA style rules).
> Originally built for a hackathon; this repository is the maintained version used for
> **Hack-with-Bengaluru selection** — shared so teammates (and any AI assistant) can understand
> and run it quickly.

**Status:** working & demo-ready · **Stack:** Python 3.10+ / FastAPI / SQLite / vanilla JS (no build step) · **Real LLM:** Groq (`openai/gpt-oss-120b`), with a deterministic local fallback engine so the demo **never breaks without keys**.

---

## 1. What is this, in one paragraph?

BharatApex AI is a **customer-service agent for a bank**, exposed through a premium dark dashboard
at `http://127.0.0.1:8000`. A user logs in as one of three synthetic bank customers, and chats with
"ClientCare" — an agent that checks balances, releases SWIFT/FIRC holds, blocks/unblocks cards,
files RBI disputes, waives fees (with policy limits), converts INR↔USD, and registers travel
notices — by **calling real backend tools**, not by hallucinating. Every action and insight is
remembered in a **long-term memory engine (Vectorize Hindsight)**, so the agent answers follow-ups
with context on later days ("that wire we talked about…"). A **Benchmark button** compares this
memory-enabled agent against a classic stateless chatbot to show the difference during pitches.
Everything is sandboxed per customer: one login can only ever see its own accounts, cards,
memories and conversations.

## 2. The 30-second demo script

1. Open `http://127.0.0.1:8000`, log in as `aarav` / `Apex@101`.
2. Ask: *"Why is my $5,000 SWIFT wire from Silicon Valley Bank on hold?"* → agent recalls purpose
   code **P0802** from memory and **releases the FIRC compliance hold** (tool call, real state change).
3. Click **Benchmark** → the stateless-bot comparison shows what a normal chatbot would ask.
4. Toggle **INR / USD / Dual** in the top bar → balances re-render in both currencies.
5. Refresh the page → the conversation and history survive (SQLite persistence).

Login accounts (all synthetic, seeds are in `src/synthetic_data/customers.json`):

| Username | Password | Customer | Persona |
|----------|----------|----------|---------|
| `aarav`  | `Apex@101` | CUST-IN-101 Aarav Singhania | Premier Private & NRI Wealth (USD + NRE, SWIFT/FIRC) |
| `rajesh` | `Apex@102` | CUST-IN-102 Rajesh Sharma | MSME Vyapar trader (UPI/Soundbox weekend batches) |
| `priya`  | `Apex@103` | CUST-IN-103 Priya Patel | Youth digital (disputes, card controls, fee waiver) |

Passwords are demo defaults, overridable via `DEMO_*_PASSWORD` in `.env`.

## 3. How to run it

```powershell
# 1. Install dependencies (Python 3.10+ required)
pip install -r requirements.txt

# 2. (Optional) create .env — copy from .env.example and add keys.
#    The app runs 100% fine with NO keys: it falls back to the local engine.

# 3. Start
python run.py
# → http://127.0.0.1:8000   (dashboard + login)
# → http://127.0.0.1:8000/docs  (interactive FastAPI/Swagger docs)
```

⚠️ **Windows console note:** `run.py` prints an emoji banner. If PowerShell throws
`UnicodeEncodeError`, run with `$env:PYTHONIOENCODING="utf-8"; python run.py`
(or add the variable in `.vscode/launch.json` — it is already configured there; **F5 works as-is**).

### Environment variables (see `.env.example`)

| Variable | Purpose | If empty |
|---|---|---|
| `LLM_PROVIDER` | `groq` (recommended) / `gemini` / `openai` | local fallback engine |
| `GROQ_API_KEY` / `GROQ_MODEL` | real conversational LLM with tool-calling | local fallback engine |
| `HINDSIGHT_API_KEY`, `HINDSIGHT_BASE_URL` | Vectorize Hindsight Cloud memory | built-in local memory engine (`data/hindsight_local_banks.json`) |
| `PORT` / `HOST` | server binding | `127.0.0.1:8000` |
| `SESSION_TTL_HOURS` | server-side session lifetime | `12` |

Stale-data note: the FX rate used everywhere is **1 USD = ₹94.11** (brought in from the live
rate on 2026-11-08), and the bank's branch identity is **MG Road Corporate Branch, Bengaluru**
(`RBI/2026/BLR-049`). Customer residences remain Hyderabad-based on purpose.

## 4. What the agent can actually do (capability + compliance map)

| Capability | Rule/logic behind it | Where it lives |
|---|---|---|
| Card block / unblock | instant, zero-friction; urgent on "lost/stolen" | `src/banking/core_banking_service.py` |
| Fee waivers | courtesy waiver once per 12 months (`POL-RBI-FEE-001`), else escalate to Regional Branch Manager | same |
| Disputes + provisional credit | RBI zero-liability / customer-protection style flow | same |
| SWIFT / FIRC hold release | purpose-code memory (`P0802`) expedites hold | same |
| Currency conversion | USD↔INR at ₹94.11, zero portfolio markup, Indian digit grouping | same |
| Reminder of settlement times | weekend UPI/QR batches settle Monday 06:00 IST | same |
| Travel notices | card regions enabled on request | same |
| Compliance guardrails | never asks for PIN/CVV/OTP; escalates RBI-Ombudsman/legal threats to the Principal Nodal Officer; single-customer data isolation | `src/banking/compliance.py` |

## 5. Project structure (LLM-friendly map)

```
apex-fintech-agent/
├── run.py                       # entry point: uvicorn on 127.0.0.1:8000 (F5 profile = same)
├── requirements.txt             # FastAPI, uvicorn, python-dotenv, httpx, requests, jinja2
├── .env.example                 # key template — copy to .env (real keys never committed)
├── data/
│   ├── clientcare.db            # SQLite: sessions, conversations, messages (auto-created)
│   └── hindsight_local_banks.json  # local memory fallback store (auto-created/seeded)
├── scripts/
│   └── reset_memory.py          # wipes local memory banks, re-seeds the 3 demo customers
├── src/
│   ├── api/
│   │   └── app.py               # FastAPI app + ALL routes (§6) + static file serving
│   ├── auth.py                  # login, server-side sessions, HttpOnly `apex_session` cookie
│   ├── db.py                    # SQLite helpers (conversations/messages persist across refreshes)
│   ├── agent/                   # ★ the conversational brain
│   │   ├── orchestrator.py      # pipeline: compliance → memory recall → snapshot → LLM/tools → retain memory
│   │   ├── llm_router.py        # Groq/OpenAI/Gemini router + tool loop + post-processing + LOCAL fallback engine
│   │   ├── prompts.py           # FINTECH_SYSTEM_PROMPT (tone/rules/facts) + classification prompt
│   │   ├── tools.py             # ToolExecutor: binds tool calls to the logged-in customer only
│   │   └── comparison.py        # stateless-bot benchmark copy for the Benchmark button
│   ├── banking/                 # ★ the synthetic bank
│   │   ├── core_banking_service.py  # accounts, cards, transactions, holds, waivers, conversions (USD_INR_RATE=94.11)
│   │   └── compliance.py        # input sanitization + escalation checks
│   ├── hindsight/               # ★ memory layer (Vectorize Hindsight Cloud w/ local fallback)
│   │   ├── client_wrapper.py    # cloud client + local fallback wiring
│   │   ├── engine.py            # local memory engine (seeded facts, recall/reflect/retain)
│   │   └── types.py             # Recall/Reflect/Retain result types
│   ├── synthetic_data/          # demo world (loaded at startup)
│   │   ├── customers.json       # 3 personas, balances, memory facts
│   │   ├── transactions.json    # transaction ledger seed
│   │   ├── policies.json        # bank policies (FX, UPI caps, waiver rule, HQ, MICR)
│   │   └── data_loader.py       # loads/validates the JSON seeds
│   └── static/                  # the whole frontend (served at /)
│       ├── index.html           # layout: sidebar / top bar / stat cards / chat / wallet / history
│       ├── styles.css           # dark premium design system (orange #FF4D00 accent) + light theme
│       └── app.js               # all UI logic, fetch calls, chat rendering — no frameworks
├── tests/                       # 19 unittest tests (all mocked, no network needed)
└── WORK-*.md / *.py             # scratch files (safe to ignore)
```

### The message pipeline (read this to modify the agent)

```
user message (index.html/app.js)
   → POST /api/chat (app.py, session-checked)
   → BankingComplianceGuard.sanitize / escalation check            (banking/compliance.py)
   → Hindsight recall + reflect: memories & directives             (hindsight/, per-customer "bank")
   → _customer_snapshot(): cards/balances/last 8 txns context      (agent/orchestrator.py)
   → LLMRouter.agentic_chat / generate with history + tools:       (agent/llm_router.py)
        Groq (openai/gpt-oss-120b, ~4 tool rounds max, dedupe)
        ├─ ToolExecutor(customer_id) MUTATES bank state            (agent/tools.py → banking/)
        └─ replies post-processed (strip meta text) & enhanced
   → fallback: deterministic data-driven local engine (no CLI keys needed)
   → Hindsight retain (stores resolution as a new memory)
   → JSON: { reply, actions[], banking_action, recalled_memories[], latency_ms, ... }
   → app.js renders chat bubble + action badges; ledger/stats refresh
```

## 6. API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/login` | – | demo credentials → session cookie |
| POST | `/api/auth/logout` | ✔ | clear session |
| GET | `/api/auth/me` | ✔ | current customer profile |
| GET | `/api/overview` | ✔ | accounts, cards, transactions, tiers (drives stat cards/wallet) |
| GET | `/api/conversations` | ✔ | chat-history sidebar |
| POST | `/api/conversations` | ✔ | new chat |
| DELETE | `/api/conversations/{id}` | ✔ | delete chat |
| GET | `/api/conversations/{id}/messages` | ✔ | reload a conversation |
| POST | `/api/chat` | ✔ | send message → agent reply + actions + memories |
| POST | `/api/benchmark` | ✔ | stateless-bot vs memory-agent comparison |
| GET | `/api/health` | – | liveness |

All user-scoped endpoints are strictly isolated to the logged-in customer.

## 7. Tests

```powershell
python -m unittest discover tests
```

19 tests, fully offline/mocked: memory retention, compliance masking, FX conversion, fee policy,
routing, login/session security, per-customer conversation isolation, chat-history persistence,
and the Groq tool-calling loop. (`OK (Some noise)` = Starlette/httpx deprecation warning; ignore it.)

## 8. Known quirks / notes for contributors

- The `.env` holds real keys and is **gitignored by design** — never commit it.
- If Hindsight Cloud is unreachable, the app silently switches to local memory (log line:
  `Cloud recall error … Using local`); the demo stays fully functional.
- Model on Groq: `llama-3.3-70b-versatile` was decommissioned; use `openai/gpt-oss-120b` (current `.env`).
- Emoji banner needs UTF-8 console (see §3).
- The UI was redesigned (v3): orange-accent dark dashboard, sidebar nav, stat cards, wallet tiles,
  cash-flow chart, recent-activities table, and an INR/USD/Dual toggle bound to all money displays.

## 9. Repo / team workflow for Hack-with-BLR

- Upstream repo: `hack_with_blr_selection` (shared selection repo).
- Do not push `.env` or `data/*.json` generated stores.
- Suggested branches: `main` = stable demo, `feat/<name>-<topic>` per teammate.
- Quick check before pushing: `python -m unittest discover tests` must be green.
