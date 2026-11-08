import time
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from ..hindsight.client_wrapper import hindsight_service
from ..banking.compliance import BankingComplianceGuard
from ..banking.core_banking_service import core_banking
from .prompts import FINTECH_SYSTEM_PROMPT
from .llm_router import LLMRouter, format_inr
from .tools import ToolExecutor

SNAPSHOT_NOTICE = ("CUSTOMER SNAPSHOT (read-only, a few seconds old — CALL the banking tools before "
                   "quoting exact live figures or performing any action):")

class FinTechSupportAgent:
    """
    Enterprise Indian & Cross-Border FinTech Customer Support AI Agent powered by Hindsight Memory.
    Orchestrates compliance checking, memory retrieval, banking actions, and memory retention.
    """

    def __init__(self):
        self.llm_router = LLMRouter()
        # Multi-turn collection state for chat-driven transfers & investments
        self._pending_transfers: Dict[str, Dict[str, Any]] = {}
        self._pending_investments: Dict[str, Dict[str, Any]] = {}

    def process_message(
        self,
        customer_id: str,
        message: str,
        use_memory: bool = True,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        history: earlier turns of THIS conversation as [{"role": "user"|"assistant", "content": ...}].
        """
        history = history or []
        # Keep the window lean (last 12 messages = 6 exchanges) so replies stay fast
        # while follow-ups like "what about the other one?" still carry context.
        history = history[-12:]
        start_time = time.time()
        bank_id = f"bank_{customer_id}"

        # 1. Compliance Sanitization & Guardrails
        clean_message = BankingComplianceGuard.sanitize_user_input(message)
        is_escalated, escalation_reason = BankingComplianceGuard.check_escalation_risk(clean_message)

        # 2. Customer Profile & Core Banking State
        customer = core_banking.get_account_summary(customer_id)
        if "error" in customer:
            return {
                "error": "Customer not found",
                "customer_id": customer_id
            }

        # 3. Hindsight Memory (Recall & Reflect)
        recalled_memories: List[Dict[str, Any]] = []
        recalled_text_list: List[str] = []
        disposition: Dict[str, Any] = {}
        directives: List[str] = []

        if use_memory:
            # Recall facts from the customer's bank
            recall_response = hindsight_service.recall(bank_id=bank_id, query=clean_message, max_results=5)
            for r in recall_response.results:
                recalled_memories.append({
                    "fact": r.fact,
                    "score": r.score,
                    "type": r.type,
                    "timestamp": r.timestamp,
                    "tags": r.tags
                })
                recalled_text_list.append(r.fact)

            # Reflect on the customer's mental model and sentiment
            reflect_response = hindsight_service.reflect(bank_id=bank_id, query=clean_message)
            disposition = reflect_response.disposition
            directives = reflect_response.directives

        # 4+5. Generate the reply.
        banking_action_result: Optional[Dict[str, Any]] = None
        actions: List[Dict[str, Any]] = []
        reply_text: Optional[str] = None

        # Compact read-only snapshot of THIS customer's own state, so the model can
        # answer with specifics immediately and persona isolation is guaranteed.
        customer_snapshot = self._customer_snapshot(customer, customer_id)

        # Deterministic chat-driven transaction manager: collects transfer /
        # investment details over multiple turns and executes instantly, no LLM
        # luck involved. (Benchmark mode stays untouched.)
        if use_memory and reply_text is None:
            # Parse the RAW message: the compliance sanitizer masks account numbers
            # ("****-6789"), which the transfer flow must read unmasked.
            flow = self._chat_investment_flow(customer_id, message)
            if flow is None:
                flow = self._chat_transfer_flow(customer_id, message)
            if flow is not None:
                reply_text = flow["reply"]
                if flow.get("action_result") is not None:
                    banking_action_result = flow["action_result"]
                    actions = [banking_action_result]

        # Preferred path: real conversation + LLM tool-calling (needs a Groq key).
        if reply_text is None and use_memory and self.llm_router.agentic_available:
            agent_system_prompt = self._build_system_prompt(customer, recalled_text_list, directives,
                                                            customer_snapshot)
            result = self.llm_router.agentic_chat(
                system_prompt=agent_system_prompt,
                history=history,
                user_message=clean_message,
                tool_executor=ToolExecutor(customer_id),
            )
            if result and result["reply"]:
                reply_text = result["reply"]
                actions = result["actions"]
                banking_action_result = actions[-1] if actions else None

        # Fallback path: keyword tools + generated / built-in local reply.
        if reply_text is None:
            if use_memory:
                banking_action_result = self._determine_and_execute_tool(
                    customer_id=customer_id,
                    message=clean_message,
                    recalled_memories=recalled_text_list
                )
                if banking_action_result:
                    actions = [banking_action_result]
            # Hand the local/LLM engines the same read-only snapshot (never the live dict).
            customer_context = dict(customer)
            customer_context["recent_transactions"] = customer_snapshot["recent_transactions"]
            reply_text = self.llm_router.generate(
                system_prompt=FINTECH_SYSTEM_PROMPT,
                user_message=clean_message,
                customer_context=customer_context,
                recalled_memories=recalled_text_list,
                directives=directives,
                banking_action_result=banking_action_result,
                is_stateless=(not use_memory),
                history=history
            )

        # Tools may have changed balances / card status: refresh the snapshot.
        customer = core_banking.get_account_summary(customer_id)

        # 6. Retain New Memory (Learning from interaction)
        new_memory_id = None
        substantive = bool(actions) or len(clean_message) > 40
        if use_memory and not is_escalated and substantive:
            interaction_summary = f"Customer inquired: '{clean_message}'. Agent resolved: {reply_text[:140]}..."
            ok_actions = [a.get("action", a.get("tool", "BANKING_ACTION")) for a in actions if a.get("success")]
            if ok_actions:
                interaction_summary += f" Executed: {', '.join(ok_actions)}."

            retain_res = hindsight_service.retain(
                bank_id=bank_id,
                content=interaction_summary,
                context="live_support_conversation",
                tags=["live_interaction", "agent_resolution"]
            )
            new_memory_id = retain_res.get("id")

        duration_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "tier": customer["tier"],
            "reply": reply_text,
            "use_memory": use_memory,
            "recalled_memories": recalled_memories,
            "disposition": disposition,
            "directives": directives,
            "banking_action": banking_action_result,
            "actions": actions,
            "escalation": {
                "is_escalated": is_escalated,
                "reason": escalation_reason
            },
            "new_memory_id": new_memory_id,
            "latency_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    def _customer_snapshot(customer: Dict[str, Any], customer_id: str) -> Dict[str, Any]:
        """Compact, read-only snapshot of the logged-in customer's own data.

        Strictly scoped: built from the authenticated customer's profile and
        transactions only, so the model can never see another customer's state.
        """
        accounts = []
        for a in customer.get("accounts", []):
            accounts.append({
                "account_id": a.get("account_id"),
                "type": a.get("type"),
                "currency": a.get("currency"),
                "balance_inr": a.get("balance_inr"),
                "balance_usd": a.get("balance_usd"),
                "hold_amount": a.get("hold_amount", 0.0) or 0.0,
                "hold_reason": a.get("hold_reason", ""),
            })
        cards = [{
            "card_id": c.get("card_id"),
            "card_type": c.get("card_type"),
            "masked_number": c.get("masked_number"),
            "status": c.get("status"),
            "international_enabled": c.get("international_enabled"),
        } for c in customer.get("cards", [])]
        recent_transactions = [{
            "transaction_id": t.get("transaction_id"),
            "date": str(t.get("date", "")),
            "description": t.get("description", ""),
            "category": t.get("category", ""),
            "amount_inr": t.get("amount_inr", 0.0),
            "status": t.get("status", ""),
        } for t in core_banking.get_transactions(customer_id, limit=8)]
        return {
            "accounts": accounts,
            "cards": cards,
            "recent_transactions": recent_transactions,
            "investments": [{
                "investment_id": i.get("investment_id"),
                "product": i.get("product"),
                "amount_inr": i.get("amount_inr"),
                "rate_pct": i.get("rate_pct"),
                "tenure_months": i.get("tenure_months"),
                "status": i.get("status"),
            } for i in core_banking.get_investments(customer_id)[:8]],
            "total_liquid_inr": customer.get("total_liquid_inr"),
            "total_liquid_usd": customer.get("total_liquid_usd"),
            "upi_id": customer.get("upi_id"),
            "city": customer.get("city"),
            "branch": customer.get("branch"),
            "kyc_status": customer.get("kyc_status"),
        }

    @staticmethod
    def _build_system_prompt(
        customer: Dict[str, Any],
        memories: List[str],
        directives: List[str],
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%A, %d %B %Y, %I:%M %p IST")
        lines = [
            FINTECH_SYSTEM_PROMPT,
            "CURRENT CUSTOMER",
            f"- Name: {customer.get('name')} | Tier: {customer.get('tier')} | UPI: {customer.get('upi_id')}",
            f"- Now: {today}",
        ]
        if snapshot:
            lines.append(SNAPSHOT_NOTICE)
            lines.append(f"- Portfolio total: {format_inr(snapshot['total_liquid_inr'])} "
                         f"(~${snapshot['total_liquid_usd']:,.2f} USD)")
            for a in snapshot["accounts"]:
                hold = a.get("hold_amount") or 0.0
                hold_note = (f" — ON HOLD {format_inr(hold)}: {a['hold_reason'][:60]}" if hold else "")
                lines.append(f"- Account {a['account_id']} ({a['type']}): "
                             f"{format_inr(a['balance_inr'])}{hold_note}")
            for c in snapshot["cards"]:
                intl = "international ON" if c.get("international_enabled") else "international OFF"
                lines.append(f"- Card {c['card_id']} ({c['card_type']}): status {c['status']}, {intl}")
            lines.append(f"- UPI handle: {snapshot['upi_id']} | Branch: {snapshot['branch']}")
            for t in snapshot["recent_transactions"][:8]:
                lines.append(f"- Recent txn: {t['date'][:10]} | {t['description'][:56]} | "
                             f"{format_inr(t['amount_inr'])} | {t['status']}")
            for i in snapshot["investments"]:
                rate = f" @ {i['rate_pct']}% p.a." if i.get("rate_pct") else ""
                lines.append(f"- Holding: {i['product']} — {format_inr(i['amount_inr'])}{rate} ({i['status']})")
        if memories:
            lines.append("WHAT YOU REMEMBER ABOUT THIS CUSTOMER (long-term memory; use it naturally, don't recite it):")
            lines += [f"- {m}" for m in memories]
        if directives:
            lines.append("GUIDANCE FOR THIS CUSTOMER:")
            lines += [f"- {d}" for d in directives]
        return "\n".join(lines)

    def _determine_and_execute_tool(
        self,
        customer_id: str,
        message: str,
        recalled_memories: List[str]
    ) -> Optional[Dict[str, Any]]:
        lower = message.lower()

        # 1. Unfreeze / Unblock / Unlock card (Strict priority over freeze)
        if any(w in lower for w in ["unfreeze", "unblock", "unlock", "reactivate", "chalu karo"]):
            cust = core_banking.get_account_summary(customer_id)
            cards = cust.get("cards", [])
            card_id = cards[0]["card_id"] if cards else "CARD-PRIMARY"
            return core_banking.unfreeze_card(customer_id, card_id)

        # 2. Freeze / Block / Lock card
        if any(w in lower for w in ["freeze", "block", "lock", "lost", "stolen", "card band"]):
            cust = core_banking.get_account_summary(customer_id)
            cards = cust.get("cards", [])
            card_id = cards[0]["card_id"] if cards else "CARD-PRIMARY"
            return core_banking.freeze_card(customer_id, card_id, reason="Customer security request")

        # 3. Inward SWIFT / FIRC release (Aarav Singhania)
        if ("wire" in lower or "swift" in lower or "firc" in lower or "5000" in lower) and customer_id == "CUST-IN-101":
            return core_banking.expedite_firc_wire_hold(
                customer_id=customer_id,
                transaction_id="TXN-IN-90811",
                purpose_code="P0802"
            )

        # 4. Fee waiver / AMC reversal
        if any(w in lower for w in ["waiver", "reverse", "amc", "nach", "fee", "250", "350"]):
            eligibility = core_banking.check_fee_waiver_eligibility(customer_id)
            if eligibility["eligible"]:
                amount_to_waive = 250.00 if customer_id == "CUST-IN-103" else 150.00
                return core_banking.process_fee_waiver(
                    customer_id=customer_id,
                    fee_amount_inr=amount_to_waive,
                    reason="Automated first-time customer courtesy waiver"
                )
            else:
                return {
                    "action": "FEE_WAIVER_DENIED",
                    "requires_escalation": True,
                    "reason": eligibility["reason"]
                }

        # 5. Dispute / Unauthorized charge
        if any(w in lower for w in ["dispute", "refund", "unrecognized", "did not do", "fraud", "unauthorized", "kyu kata"]):
            txns = core_banking.get_transactions(customer_id, limit=3)
            target_id = txns[0]["transaction_id"] if txns else "TXN-IN-DISPUTE"
            return core_banking.initiate_dispute(
                customer_id=customer_id,
                transaction_id=target_id,
                reason="Unrecognized charge reported by cardholder"
            )

        # 6. Currency Conversion tool
        if any(w in lower for w in ["convert", "usd to inr", "inr to usd", "forex"]):
            amt_match = re.search(r"(\d+(?:\.\d+)?)", lower)
            amt = float(amt_match.group(1)) if amt_match else 500.0
            from_c = "INR" if ("rupee" in lower and "dollar" not in lower) else "USD"
            to_c = "USD" if from_c == "INR" else "INR"
            return core_banking.convert_currency(amt, from_c, to_c)

        # 7. Travel notice
        if any(w in lower for w in ["travel notice", "travelling to", "flying to", "going to dubai", "going to london"]):
            dest = "Dubai / Western Europe"
            if "dubai" in lower: dest = "Dubai, UAE"
            elif "london" in lower: dest = "London, UK"
            elif "singapore" in lower: dest = "Singapore"
            elif "san francisco" in lower or "us" in lower: dest = "San Francisco, USA"

            return {
                "success": True,
                "action": "TRAVEL_NOTICE_REGISTERED",
                "destination": dest,
                "message": f"Zero-forex travel clearance placed for {dest}."
            }

        return None

    # --------------------------------------------------------------
    # Deterministic chat-driven transaction manager (transfers & investments)
    # Runs across turns: asks for mode → receiver UPI ID / name+account+IFSC →
    # amount, then executes and confirms — independent of any LLM provider.
    # --------------------------------------------------------------
    _OTHER_TOPIC_RE = re.compile(
        r"\b(balance|limits?|block|unblock|freeze|dispute|refund|waiver|swift|firc|"
        r"convert|interest|amc|nach|loan|emi|travel|soundbox|settlement)\b")

    @staticmethod
    def _parse_amount(text: str) -> Optional[float]:
        t = text.lower()
        # 1) currency-prefixed amounts (₹5000, rs. 2,500, inr 1.2 lakh)
        m = re.search(r"(?:₹|rs\.?|inr|rupees)\s*([\d][\d,]*(?:\.\d+)?)\s*(k\b|lakh|lac|l\b|cr\b|crore)?", t)
        # 2) suffixed amounts (5000 rs, 25k, 1.5 lakh)
        if not m:
            m = re.search(r"\b([\d][\d,]*(?:\.\d+)?)\s*(k\b|lakh|lac|l\b|cr\b|crore)", t)
        if m:
            amt = float(m.group(1).replace(",", ""))
            mult = {"k": 1e3, "lakh": 1e5, "lac": 1e5, "l": 1e5, "cr": 1e7, "crore": 1e7}
            return round(amt * mult.get((m.group(2) or "").strip(), 1.0), 2)
        # 3) bare numbers — but skip account-number-length digit runs
        for m in re.finditer(r"\b([\d][\d,]*(?:\.\d+)?)\b", t):
            digits = m.group(1).replace(",", "")
            if len(digits) <= 9:
                return float(digits)
        return None

    @classmethod
    def _extract_receiver_name(cls, message: str) -> Optional[str]:
        parts = re.split(r"\b(?:to|for)\b", message, maxsplit=1, flags=re.I)
        if len(parts) < 2:
            return None
        part = re.split(r"[@\d]", parts[1])[0]
        part = re.split(
            r"\s+\b(?:via|through|by|with|on|at|account|a/c|ac|ifsc|rs|rupees|inr|amount|"
            r"upi|rtgs|neft|imps|id|please|now|instantly|immediately|bank)\b",
            part, flags=re.I)[0]
        words = [w for w in part.strip().split(" ") if w]
        while words and words[-1].lower() in ("and", "the"):
            words.pop()
        while words and words[0].lower() in ("my", "the", "a", "an"):
            words.pop(0)
        name = " ".join(words).strip(" .,,-?!'")
        if name and 2 <= len(name) <= 60 and re.match(r"^[A-Za-z .\-']+$", name):
            return name
        return None

    def _extract_transfer_fields(self, message: str) -> Dict[str, Any]:
        lower = message.lower()
        fields: Dict[str, Any] = {}
        for rail in ("upi", "rtgs", "neft", "imps"):
            if re.search(rf"\b{rail}\b", lower):
                fields["mode"] = rail.upper()
                break
        amt = self._parse_amount(message)
        if amt:
            fields["amount"] = amt
        vpa = re.search(r"[A-Za-z0-9.\-_]{2,}@[A-Za-z]{2,}", message)
        if vpa and not re.search(r"@(gmail|yahoo|outlook|hotmail|icloud|rediffmail|proton)\.",
                                 vpa.group(0), re.I):
            fields["upi_id"] = vpa.group(0).lower()
        ifsc = re.search(r"\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b", message.upper())
        if ifsc:
            fields["ifsc_code"] = ifsc.group(0).upper()
        acc = re.search(r"\b\d{9,18}\b", lower)
        if acc:
            fields["account_number"] = acc.group(0)
        name = self._extract_receiver_name(message)
        if name:
            fields["beneficiary_name"] = name
        return fields

    def _chat_transfer_flow(self, customer_id: str, message: str) -> Optional[Dict[str, Any]]:
        lower = message.lower()

        if re.search(r"\b(cancel|never mind|not now)\b", lower):
            if self._pending_transfers.pop(customer_id, None) is not None:
                return {"reply": ("No problem — the pending transfer is cancelled. "
                                  "Say 'send money' whenever you want to start fresh.")}
            return None

        pending = dict(self._pending_transfers.get(customer_id) or {})
        in_flow = customer_id in self._pending_transfers
        fields = self._extract_transfer_fields(message)
        is_start = bool(re.search(r"\b(send|transfer|remit|bhej|bhejo|pay)\b", lower)) \
            and not self._OTHER_TOPIC_RE.search(lower)
        has_detail = bool(fields)

        if not in_flow and not is_start:
            return None
        if in_flow and not has_detail and not is_start:
            # Customer moved on to another topic — drop the pending transfer
            self._pending_transfers.pop(customer_id, None)
            return None

        pending.update({k: v for k, v in fields.items() if v})
        self._pending_transfers[customer_id] = pending

        # Infer the rail from whatever receiver info we already have
        if not pending.get("mode"):
            if pending.get("upi_id"):
                pending["mode"] = "UPI"
            elif pending.get("ifsc_code") or pending.get("account_number"):
                pending["mode"] = "NEFT"
        mode = pending.get("mode")
        amount = pending.get("amount")

        if not mode:
            return {"reply": (
                "Absolutely — I can send that for you right now. Which **mode** should I use?\n\n"
                "• **UPI** — instant & free (needs the receiver's UPI ID)\n"
                "• **IMPS / NEFT** — needs name + account number + IFSC\n"
                "• **RTGS** — real-time, for **₹2,00,000** and above\n\n"
                "And tell me the **amount** and the **receiver's UPI ID** (or their name + account "
                "number + IFSC) — the moment I have everything, the money moves.")}

        if not amount:
            if mode == "UPI":
                return {"reply": (
                    f"Got it — **UPI** it is. How much should I send, and to which "
                    f"**UPI ID** (name@bank)? Give me both and it goes out instantly.")}
            return {"reply": (
                f"Got it — **{mode}**. Now I need: • the **amount** • the beneficiary's "
                f"**full name** • their **account number** • their bank's **IFSC code**.")}

        missing: List[str] = []
        if mode == "UPI":
            if not pending.get("upi_id"):
                missing.append("the receiver's UPI ID (name@bank)")
        else:
            if not pending.get("beneficiary_name"):
                missing.append("the beneficiary's full name")
            if not pending.get("account_number"):
                missing.append("their account number")
            if not pending.get("ifsc_code"):
                missing.append("their bank's IFSC code")
        if missing:
            return {"reply": (
                f"Almost there — to send **{format_inr(amount)}** via **{mode}** I still need: "
                f"{', '.join(missing)}. Reply with it and the money goes out instantly.")}

        # Everything collected — execute the transfer immediately
        self._pending_transfers.pop(customer_id, None)
        res = core_banking.execute_transfer(
            customer_id,
            mode=mode,
            amount_inr=amount,
            upi_id=pending.get("upi_id"),
            beneficiary_name=pending.get("beneficiary_name"),
            account_number=pending.get("account_number"),
            ifsc_code=pending.get("ifsc_code"),
            note=pending.get("beneficiary_name"),
        )
        if res.get("success"):
            if mode == "UPI":
                to_label = pending.get("upi_id", "receiver")
            else:
                to_label = "{} (a/c ••••{}, IFSC {})".format(
                    pending.get("beneficiary_name", "beneficiary"),
                    str(pending.get("account_number", ""))[-4:],
                    pending.get("ifsc_code", ""))
            reply = (
                "✅ **Transfer successful!**\n\n"
                f"• **{format_inr(res['amount_inr'])}** sent via **{mode}** to **{to_label}**\n"
                f"• Payment ID `{res['transaction_id']}` • UTR `{res['utr_ref']}`\n"
                f"• Status: **{res['status']}**\n"
                f"• `{res['debited_account_id']}` now shows **{format_inr(res['new_account_balance_inr'])}** "
                "— your dashboard balance and Recent Activities have updated instantly.")
            return {"reply": reply, "action_result": res}

        # Bounced by rail rules (limits / invalid VPA / insufficient funds)
        hint = ""
        if "UPI per-transaction limit" in str(res.get("error", "")):
            hint = "\n\nWant me to use **RTGS** (give me the beneficiary's name, account number and IFSC) instead?"
        return {"reply": f"⚠️ {res.get('error', 'The transfer could not be completed.')}{hint}",
                "action_result": res}

    _INVEST_HINTS = [
        ("tax saver", "3-Yr Tax Saver Fixed Deposit"),
        ("80c", "3-Yr Tax Saver Fixed Deposit"),
        ("nifty", "Nifty 50 Index Fund SIP"),
        ("index fund", "Nifty 50 Index Fund SIP"),
        ("sip", "Nifty 50 Index Fund SIP"),
        ("liquid", "Apex Liquid Mutual Fund (Sweep)"),
        ("bond", "Corporate Bond Fund"),
        ("recurring", "Apex Smart Recurring Deposit"),
        ("gold", "Apex Digital Gold Saver"),
        ("nre", "NRE Fixed Deposit"),
        ("fixed deposit", "Apex 1-Yr Fixed Deposit"),
        ("fd", "Apex 1-Yr Fixed Deposit"),
        ("usd", "USD Foreign-Currency Fixed Deposit"),
    ]

    @classmethod
    def _match_product(cls, lower: str) -> Optional[str]:
        for hint, label in cls._INVEST_HINTS:
            if hint in lower:
                return label
        return None

    def _chat_investment_flow(self, customer_id: str, message: str) -> Optional[Dict[str, Any]]:
        lower = message.lower()
        if re.search(r"\b(cancel|never mind|not now)\b", lower):
            if self._pending_investments.pop(customer_id, None) is not None:
                return None

        pending = dict(self._pending_investments.get(customer_id) or {})
        product = self._match_product(lower)
        amount = self._parse_amount(message)
        create_verb = bool(re.search(r"\b(book|invest|investing|put|place|start|open|"
                                     r"go ahead|proceed|confirm|yes|sure|do it)\b", lower))
        rec_verb = bool(re.search(r"\b(recommend|recommendation|suggest|suggestion|advice|advise|"
                                  r"viable|option|options|where should i|invest my|good place)\b", lower))

        # Option-number replies ("1", "option 2", "second one") to earlier recommendations
        if not product and pending.get("recommendations"):
            recs = pending["recommendations"]
            stripped = message.strip().lower()
            idx = None
            if re.fullmatch(r"\d", stripped):
                idx = stripped
            else:
                m = re.search(r"\boption\s+([1-9])\b", stripped) \
                    or re.search(r"\b(first|second|third|fourth|one|two|three|four)\b", stripped)
                if m:
                    idx = m.group(1) if m.group(1).isdigit() else \
                        {"one": "1", "two": "2", "three": "3", "four": "4",
                         "first": "1", "second": "2", "third": "3", "fourth": "4"}[m.group(1)]
            if idx is not None and 1 <= int(idx) <= len(recs):
                product = recs[int(idx) - 1]["product"]

        # 1) Everything present → book it immediately
        if product and amount and (create_verb or pending.get("recommendations")
                                   or re.search(r"\binvest\b", lower)):
            self._pending_investments.pop(customer_id, None)
            res = core_banking.create_investment(customer_id, product, amount)
            if res.get("success"):
                return {"reply": (
                    "✅ **Investment booked!** It's now in your **Investments & Savings** tab.\n\n"
                    f"• **{res['product']}** — **{format_inr(res['amount_inr'])}** @ **{res['rate_pct']}% p.a.** "
                    f"for **{res['tenure_months']} months**\n"
                    f"• ID `{res['investment_id']}` • est. maturity "
                    f"**{format_inr(res['expected_maturity_value_inr'])}** on {res['maturity_date'][:10]}\n"
                    f"• Debited from `{res['debited_account_id']}` — your dashboard balance has updated."),
                        "action_result": res}
            return {"reply": f"⚠️ {res.get('error')}", "action_result": res}

        # 2) Product known but no amount → ask for the amount
        if product and not amount and (create_verb or pending.get("recommendations")):
            self._pending_investments[customer_id] = {**pending, "product": product}
            return {"reply": (f"Great choice — how much should I put into "
                              f"**{product}**? Your investable surplus is "
                              f"**{format_inr(core_banking._investable_surplus(customer_id))}**.")}

        # 3) Amount known but no product → ask which product
        if amount and create_verb and not product and pending.get("recommendations"):
            lines = [f"**{i + 1}. {r['product']}**" for i, r in enumerate(pending["recommendations"])]
            return {"reply": (f"Which one should I invest **{format_inr(amount)}** in?\n\n"
                              + "\n".join(lines) +
                              "\n\nJust reply with the option number.")}

        # 4) Recommendation request → present the shortlist
        if rec_verb and not product:
            res = core_banking.get_investment_recommendations(customer_id)
            self._pending_investments[customer_id] = {
                "recommendations": res["recommendations"], "product": None}
            lines = []
            for i, r in enumerate(res["recommendations"], 1):
                lines.append(f"{i}. **{r['product']}** — indicative **{r['indicative_rate_pct']}% p.a.** • "
                             f"risk: {r['risk']} • min **{format_inr(r['min_amount_inr'])}**\n"
                             f"    _{r['why']}_")
            return {"reply": (
                f"Based on your **{res['customer_tier']}** profile (investable surplus: "
                f"**{format_inr(res['investable_surplus_inr'])}**), these are the most viable options right now:\n\n"
                + "\n".join(lines) +
                "\n\nSay **'invest ₹X in option N'** (or 'invest ₹X in <product name>') and I'll book it — "
                "it will appear instantly in your **Investments & Savings** tab.\n\n"
                "_Indicative returns only; market-linked options aren't guaranteed._")}

        return None

support_agent = FinTechSupportAgent()
