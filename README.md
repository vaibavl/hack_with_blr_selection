# 🏛️ BharatApex AI — Enterprise Indian & Global FinTech Banking Agent
### Built for HackwithHyderabad 3.0 • Powered by Vectorize Hindsight Memory Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Hindsight Memory](https://img.shields.io/badge/Hindsight-Vectorize-6366f1.svg?style=flat)](https://github.com/vectorize-io/hindsight)
[![RBI & NPCI](https://img.shields.io/badge/Banking_Rails-UPI_%7C_RuPay_%7C_SWIFT-ff9933.svg?style=flat)](https://www.npci.org.in/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

**BharatApex AI** is an enterprise-grade, market-ready **FinTech Customer Support AI Agent** specifically architected for the Indian banking landscape with seamless cross-border global trade capabilities. Engineered with **Vectorize Hindsight Memory**, it eliminates the #1 customer pain point in banking: *having to repeat your story across multiple calls and tickets*.

Located at our **MG Road Corporate Branch in Bengaluru**, BharatApex AI handles **UPI dispute resolution**, **FIRC cross-border inward SWIFT remittances**, **merchant QR Soundbox settlements**, **instant card block/unblock**, **RBI courtesy fee waivers**, and **live dual-currency (₹ INR & $ USD) conversions**.

---

## ✨ Core Features

- **Customer login** — username/password sign-in for three synthetic customers, backed by server-side sessions and an `HttpOnly` `apex_session` cookie.
- **Strict persona isolation** — each login sees exactly one customer's accounts, cards, memories, and conversations. There is no in-app persona switcher.
- **Persistent chat history** — a ChatGPT-style right-hand **Chat History** panel with New Chat, rename, and delete; conversations survive page refreshes.
- **Long-term banking memory** — Vectorize Hindsight Cloud when configured, with the built-in local Hindsight engine as a zero-key fallback.
- **Account Overview** — the live banking ledger (formerly the core banking ledger panel) with accounts, cards, balances, and holds.
- **Currency modes** — one-click **INR**, **USD**, and **Dual (₹ + $)** display toggle.
- **Conversational chatbot** — with a Groq key the assistant holds a real multi-turn conversation (it sees the earlier messages in the chat) and uses *tool calling* to check balances/transactions and to block or unblock cards, file disputes, request fee waivers, release SWIFT holds, convert currency and register travel notices. Tools are bound to the logged-in customer, so the model can never touch another customer's data. Without a key, a deterministic local engine answers instead.
- **Demo extras** — Hindsight On/Off benchmark comparison, quick-prompt scenarios, dark/bright theme toggle, and voice input.

---

## 🌟 Why This Wins at HackwithHyderabad 3.0: The Hindsight Difference

Stateless chatbots frustrate Indian banking customers by demanding manual branch visits, Form 60 resubmissions, and repetitive KYC verifications.

With **Vectorize Hindsight Memory**, BharatApex AI:
1. **Remembers Regulatory Purpose Codes**: Remembers that NRI tech founder Aarav uses purpose code `P0802` (Software Consultancy) for US inward wires, expediting FIRC release in **15 minutes** instead of 5 days.
2. **Tracks Rolling Fee Waiver Rules**: Enforces RBI courtesy waiver limits. Recognizes when an MSME trader (Rajesh) already used his 12-month courtesy waiver, politely escalating to the Regional Branch Manager rather than giving conflicting answers.
3. **Protects Working Capital**: Understands that Begum Bazaar trader Rajesh needs weekend UPI collections cleared by Monday 06:00 IST to fund vendor dispatches.
4. **Instant Security Actions**: Allows zero-friction card unblocking and instantly flags unauthorized electronic transactions under RBI Zero-Liability guidelines.

---

## 👥 Realistic Indian Personas Pre-Loaded

| Customer | Persona & Profile | Financial Context & Memory Nuances |
| :--- | :--- | :--- |
| **Aarav Singhania** (`CUST-IN-101`) | **Premier Private & NRI Wealth**<br>Hyderabad & San Francisco | **₹28,50,000 NRE Checking + $45,000 USD Reserve**.<br>Frequently wires funds from Silicon Valley Bank for tech investments. Recalls past FIRC hold on $5,000 wire; prefers concise executive WhatsApp updates. |
| **Rajesh Sharma** (`CUST-IN-102`) | **MSME Vyapar Trader**<br>Begum Bazaar, Hyderabad | **₹14,20,500 Current Account + ₹3,85,000 QR Batch**.<br>Depends on weekend Soundbox UPI batches for Monday supplier dispatches. Used a one-time courtesy NACH bounce waiver last month. |
| **Priya Patel** (`CUST-IN-103`) | **Youth Digital / Software Engineer**<br>HITEC City, Hyderabad | **₹62,400 DigiSavings + $1,250 Forex Wallet**.<br>Zero penalty history with a 790 CIBIL score. Eligible for instant automated waiver of annual card fees. Reported recurring international subscription dispute. |

---

## 🔐 Login & Demo Accounts

Start the app and sign in at **[http://127.0.0.1:8000](http://127.0.0.1:8000)** with one of the synthetic demo accounts:

| Username | Password | Customer | Profile |
| :--- | :--- | :--- | :--- |
| `aarav` | `Apex@101` | Aarav Singhania (`CUST-IN-101`) | Premier Private & NRI Wealth |
| `rajesh` | `Apex@102` | Rajesh Sharma (`CUST-IN-102`) | MSME Vyapar Trader |
| `priya` | `Apex@103` | Priya Patel (`CUST-IN-103`) | Youth Digital / Software Engineer |

- **One login, one customer.** Each session is isolated to the authenticated customer and can only see that customer's accounts, cards, memories, and chat history.
- **No persona switching inside the app.** To view another demo customer, log out and sign in with that customer's credentials.
- Sessions are server-side and carried by the `HttpOnly` **`apex_session`** cookie; the default lifetime is 12 hours (`SESSION_TTL_HOURS`).
- Conversations, messages, and other application data are persisted in SQLite at `data/clientcare.db` (configurable via `DATABASE_PATH`).
- The demo passwords above are defaults and can be overridden with the `DEMO_*_PASSWORD` variables in `.env`.

---

## 🕘 Chat History

The right-hand **Chat History** panel replaces the old Hindsight Memory Bank inspector. It works like a ChatGPT conversation sidebar:

- **Persistent conversations** — chats are stored in SQLite and restored after a page refresh.
- **New Chat** — start a fresh thread without losing earlier conversations.
- **Rename / Delete** — organize or remove conversations from the panel.
- **Per-customer scope** — history belongs to the logged-in customer and is never shared between accounts.
- The **Account Overview** panel (the renamed banking ledger) continues to show live accounts, cards, balances, and holds, with the INR / USD / Dual toggle available in the top bar.

---

## 🧠 Memory: Hindsight Cloud with Local Fallback

BharatApex AI remembers each customer's case history through Vectorize Hindsight.

- **Local fallback (default):** leave `HINDSIGHT_API_KEY` and `HINDSIGHT_BASE_URL` blank (or skip `.env` entirely). The built-in local engine seeds memory from the synthetic customer profiles and persists it to `data/hindsight_local_banks.json`. No network or API key is required.
- **Hindsight Cloud:** open the existing `.env` file (`.env.example` is kept only as a reference template) and set:

  ```env
  HINDSIGHT_API_KEY=your_hindsight_api_key
  HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
  ```

  The agent uses the cloud service when it is reachable and automatically falls back to the local engine if a request fails, so the demo keeps working either way.

To reset local memory to the clean seeded baseline, run:

```powershell
python scripts/reset_memory.py
```

This removes every local bank (including leftover test banks such as `test_bank_cust_in_999`) and re-seeds the three demo customers.

---

## ⚡ LLM Setup: Groq with Local Fallback

The agent ships with a deterministic local FinTech reasoning engine, so the demo works with zero API keys. For generative, natural-language replies, Groq's fast free tier is recommended:

1. Create a free API key at **[console.groq.com](https://console.groq.com/)**.
2. Open the existing `.env` file in the project root (it is already created; `.env.example` is only a reference).
3. Set the following values:

   ```env
   LLM_PROVIDER=groq
   GROQ_API_KEY=your_groq_api_key
   GROQ_MODEL=openai/gpt-oss-120b
   ```

If the key is blank or a Groq request fails, the agent automatically falls back to the local engine. Optional Gemini and OpenAI keys are also documented in `.env.example`.

---

## 🚀 How to Run in Visual Studio Code (Step-by-Step)

### Prerequisites
- **Python 3.10+**
- Install dependencies from the project root:
  ```powershell
  pip install -r requirements.txt
  ```

### Option 1: One-Click Run with F5 (Recommended)
1. Open **VS Code**.
2. Go to **File** > **Open Folder...** and open the project folder (the folder containing `run.py`).
3. *(Optional)* Open `.env` and add any API keys you want to use. It is already present; `.env.example` is only a template.
4. Press **`F5`** on your keyboard (or click **Run and Debug** on the left bar and choose **Run Apex FinTech Agent (FastAPI)**).
5. The server will launch in your integrated terminal.
6. Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)** and log in with a demo account from the table above.

### Option 2: Run via VS Code Terminal
1. Open the project folder in VS Code, then open the integrated terminal (`Ctrl + ~` or **Terminal** > **New Terminal**).
2. Start the application:
   ```powershell
   python run.py
   ```
3. Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)** and log in.
   *(Interactive Swagger documentation is available at **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**.)*

---

## 🎯 60-Second Judge Pitch Demo Script

Follow this sequence to showcase the system to judges:

### 1. Show the NRI Cross-Border SWIFT & FIRC Memory
- Log in as **aarav / Apex@101** (Aarav, NRI Wealth).
- Click Quick Scenario: *"Why is my $5,000 SWIFT wire from Silicon Valley Bank on hold?"*
- **Judge Impact**: The agent recalls his Oct 24th transfer, recognizes Purpose Code `P0802`, and releases the FIRC compliance hold in 15 minutes!
- Click **Benchmark** to show what a traditional stateless chatbot does (asks him to take physical documents to a branch and wait 5 days).

### 2. Show the Multi-Currency Converter
- Ask: *"Convert $1,200 USD to INR"* or toggle the currency switcher to **Dual (₹ + $)** in the top navigation.
- **Judge Impact**: Calculates real-time interbank rate ($1 = ₹94.11) with zero-markup forex benefits!

### 3. Show the MSME Trader Weekend Liquidity & Policy Memory
- Log out, then log in as **rajesh / Apex@102** (Rajesh, MSME Vyapar).
- Click Quick Scenario: *"Where is my weekend Soundbox & QR collection of ₹3,85,000?"*
- **Judge Impact**: Confirms Batch #HYD-9021 from 342 payments clearing at Monday 06:00 IST to protect his Begum Bazaar supplier cycle.
- Ask: *"Can you waive my NACH return fee?"*
- **Judge Impact**: Recalls he already received a ₹350 waiver on Oct 5th; enforces `POL-RBI-FEE-001` and escalates to Regional Manager for exception approval.

### 4. Show Card Unblock & Instant Zero-Liability Dispute
- Log out, then log in as **priya / Apex@103** (Priya, Youth Tech).
- Click: *"I did not authorize the ₹899 international cloud charge, please refund me."*
- **Judge Impact**: Registers formal RBI Grievance Dispute `DSP-RBI-7041` with 24-hr provisional credit under RBI Customer Protection Charter, and disables international e-com transactions.
- Click: *"Please unblock my RuPay card right now."*
- **Judge Impact**: Instantly reactivates card with zero friction.

### 5. Show Persistent Chat History & Persona Isolation
- Refresh the page: the current conversation and its messages are still there.
- In the right-hand **Chat History** panel, start a **New Chat**, rename it, and delete a conversation.
- **Judge Impact**: Unlike a stateless demo, conversations persist across refreshes, and each login remains isolated to its own customer.

---

## 🧪 Automated Test Verification

Run all tests from the project root:
```powershell
python -m unittest discover tests
```

The suite contains 19 tests covering memory retention, compliance masking, dual currency conversion, fee policies, conversational routing, login/session security, per-customer conversation isolation, chat-history persistence, and the Groq tool-calling loop (mocked, no network needed).
