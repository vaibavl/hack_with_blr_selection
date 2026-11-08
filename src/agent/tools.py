"""Banking tools the chatbot can call. Every tool is bound to ONE authenticated
customer, so the model can never act on (or see) another customer's data."""

import json
from typing import Any, Dict, List

from ..banking.core_banking_service import core_banking, USD_INR_RATE

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "get_account_summary",
        "description": "Get the customer's live accounts, balances, holds, total portfolio value and registered cards.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_recent_transactions",
        "description": "List the customer's most recent transactions with IDs, amounts, status and UTR reference.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "How many to return (1-10)", "default": 5}}}}},
    {"type": "function", "function": {
        "name": "block_card",
        "description": "Immediately freeze/block the customer's card (lost, stolen, or customer request).",
        "parameters": {"type": "object", "properties": {
            "card_id": {"type": "string", "description": "Optional card_id. Defaults to the primary card."}}}}},
    {"type": "function", "function": {
        "name": "unblock_card",
        "description": "Reactivate / unblock the customer's frozen card.",
        "parameters": {"type": "object", "properties": {
            "card_id": {"type": "string", "description": "Optional card_id. Defaults to the primary card."}}}}},
    {"type": "function", "function": {
        "name": "request_fee_waiver",
        "description": "Check policy POL-RBI-FEE-001 and, if eligible, credit a courtesy fee waiver. If not eligible, returns the reason and that escalation is needed.",
        "parameters": {"type": "object", "properties": {
            "fee_amount_inr": {"type": "number", "description": "Fee amount in INR"},
            "fee_type": {"type": "string", "description": "e.g. NACH return fee, card AMC"}},
            "required": ["fee_amount_inr"]}}},
    {"type": "function", "function": {
        "name": "raise_dispute",
        "description": "File a formal RBI zero-liability dispute for an unauthorized or unrecognised transaction.",
        "parameters": {"type": "object", "properties": {
            "transaction_id": {"type": "string", "description": "Transaction ID from get_recent_transactions"},
            "reason": {"type": "string"}},
            "required": ["transaction_id", "reason"]}}},
    {"type": "function", "function": {
        "name": "release_swift_hold",
        "description": "Release the FIRC compliance hold on an inward SWIFT wire using the customer's standing purpose code.",
        "parameters": {"type": "object", "properties": {
            "transaction_id": {"type": "string"},
            "purpose_code": {"type": "string", "description": "RBI purpose code, e.g. P0802"}},
            "required": ["transaction_id"]}}},
    {"type": "function", "function": {
        "name": "convert_currency",
        "description": "Convert between USD and INR at the bank's interbank rate.",
        "parameters": {"type": "object", "properties": {
            "amount": {"type": "number"},
            "from_currency": {"type": "string", "enum": ["USD", "INR"]},
            "to_currency": {"type": "string", "enum": ["USD", "INR"]}},
            "required": ["amount", "from_currency", "to_currency"]}}},
    {"type": "function", "function": {
        "name": "register_travel_notice",
        "description": "Register an international travel notice so the card is not declined abroad.",
        "parameters": {"type": "object", "properties": {
            "destination": {"type": "string"}},
            "required": ["destination"]}}},
    {"type": "function", "function": {
        "name": "send_money",
        "description": ("Execute a money transfer for the customer on UPI, RTGS, NEFT or IMPS rails and debit their "
                        "balance immediately. For UPI you MUST have the receiver's UPI ID. For RTGS/NEFT/IMPS you must "
                        "have the beneficiary name, account number and IFSC. If any required detail is missing, ASK the "
                        "customer in chat first — do NOT guess or fabricate placeholders."),
        "parameters": {"type": "object", "properties": {
            "mode": {"type": "string", "enum": ["UPI", "RTGS", "NEFT", "IMPS"],
                     "description": "Payment rail. Ask the customer which mode they want if not clear from context."},
            "amount_inr": {"type": "number", "description": "Amount to send in INR"},
            "upi_id": {"type": "string", "description": "Receiver's UPI ID (required for UPI)"},
            "beneficiary_name": {"type": "string", "description": "Receiver's full name (required for RTGS/NEFT/IMPS)"},
            "account_number": {"type": "string", "description": "Receiver's account number (required for RTGS/NEFT/IMPS)"},
            "ifsc_code": {"type": "string", "description": "Receiver's bank IFSC code (required for RTGS/NEFT/IMPS)"},
            "note": {"type": "string", "description": "Optional remark / purpose of payment"}},
            "required": ["mode", "amount_inr"]}}},
    {"type": "function", "function": {
        "name": "get_investment_recommendations",
        "description": ("Get personalized, viable investment recommendations (FDs, liquid funds, corporate bonds, index "
                        "SIPs, NRE/USD deposits...) based on the customer's tier and investable surplus. Always call this "
                        "BEFORE recommending any investment."),
        "parameters": {"type": "object", "properties": {
            "goal": {"type": "string", "description": "Optional goal stated by the customer, e.g. 'tax saving', 'car purchase'"}}}}},
    {"type": "function", "function": {
        "name": "get_investment_portfolio",
        "description": "List the customer's current investments & savings holdings (including FD accounts and new bookings).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "create_investment",
        "description": ("Book a new investment for the customer from their liquid balance after they explicitly agree. "
                        "Debits the amount immediately and adds it to their Investments & Savings tab."),
        "parameters": {"type": "object", "properties": {
            "product": {"type": "string",
                        "description": "One of the recommended products, e.g. 'Nifty 50 Index Fund SIP', '3-Yr Tax Saver Fixed Deposit', 'Apex 1-Yr Fixed Deposit', 'Liquid Mutual Fund', 'Corporate Bond Fund', 'Recurring Deposit', 'NRE Fixed Deposit', 'USD Fixed Deposit'"},
            "amount_inr": {"type": "number", "description": "Amount to invest in INR"},
            "tenure_months": {"type": "integer", "description": "Optional tenure override in months"},
            "goal": {"type": "string", "description": "Optional goal this investment is for"}},
            "required": ["product", "amount_inr"]}}},
]


class ToolExecutor:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id

    # ------------------------------------------------------------ helpers
    def _cards(self) -> List[Dict[str, Any]]:
        return core_banking.get_account_summary(self.customer_id).get("cards", [])

    def _resolve_card(self, card_id: str = None):
        cards = self._cards()
        if not cards:
            return None
        if card_id:
            for c in cards:
                if c["card_id"].lower() == card_id.lower():
                    return c["card_id"]
        return cards[0]["card_id"]

    # -------------------------------------------------------------- run
    def run(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            fn = getattr(self, f"_t_{name}", None)
            if fn is None:
                return {"success": False, "error": f"Unknown tool {name}"}
            return fn(**(args or {}))
        except TypeError as e:
            return {"success": False, "error": f"Bad arguments: {e}"}
        except Exception as e:  # never let a tool crash the chat
            return {"success": False, "error": str(e)}

    def _t_get_account_summary(self):
        s = core_banking.get_account_summary(self.customer_id)
        return {k: s[k] for k in ("name", "tier", "upi_id", "branch", "ifsc", "accounts",
                                   "total_liquid_inr", "total_liquid_usd", "cards", "fx_rate")}

    def _t_get_recent_transactions(self, limit: int = 5):
        limit = max(1, min(int(limit), 10))
        return {"transactions": core_banking.get_transactions(self.customer_id, limit=limit)}

    def _t_block_card(self, card_id: str = None):
        cid = self._resolve_card(card_id)
        if not cid:
            return {"success": False, "error": "No card on file"}
        r = core_banking.freeze_card(self.customer_id, cid, reason="Customer security request")
        r["action"] = "FREEZE_CARD"
        return r

    def _t_unblock_card(self, card_id: str = None):
        cid = self._resolve_card(card_id)
        if not cid:
            return {"success": False, "error": "No card on file"}
        return core_banking.unfreeze_card(self.customer_id, cid)

    def _t_request_fee_waiver(self, fee_amount_inr: float, fee_type: str = "fee"):
        elig = core_banking.check_fee_waiver_eligibility(self.customer_id)
        if not elig["eligible"]:
            return {"success": False, "action": "FEE_WAIVER_DENIED", "requires_escalation": True,
                    "reason": elig["reason"]}
        return core_banking.process_fee_waiver(
            self.customer_id, float(fee_amount_inr), f"Courtesy waiver: {fee_type}")

    def _t_raise_dispute(self, transaction_id: str, reason: str):
        mine = {t["transaction_id"] for t in core_banking.get_transactions(self.customer_id, limit=50)}
        if transaction_id not in mine:
            return {"success": False, "error": "That transaction ID is not on this customer's account."}
        return core_banking.initiate_dispute(self.customer_id, transaction_id, reason)

    def _t_release_swift_hold(self, transaction_id: str, purpose_code: str = "P0802"):
        txns = {t["transaction_id"]: t for t in core_banking.get_transactions(self.customer_id, limit=50)}
        t = txns.get(transaction_id)
        if not t or "Hold" not in t.get("status", "") or self.customer_id != "CUST-IN-101":
            return {"success": False,
                    "error": "No inward wire under compliance hold found for this customer/transaction."}
        return core_banking.expedite_firc_wire_hold(self.customer_id, transaction_id, purpose_code)

    def _t_convert_currency(self, amount: float, from_currency: str, to_currency: str):
        return core_banking.convert_currency(float(amount), from_currency, to_currency)

    def _t_register_travel_notice(self, destination: str):
        return {"success": True, "action": "TRAVEL_NOTICE_REGISTERED", "destination": destination,
                "message": f"Travel notice registered for {destination}. Card whitelisted for POS/ATM there."}

    def _t_send_money(self, mode: str, amount_inr: float, upi_id=None, beneficiary_name=None,
                      account_number=None, ifsc_code=None, note=None):
        if account_number is not None:
            account_number = str(account_number).strip()
        return core_banking.execute_transfer(
            self.customer_id,
            mode=mode,
            amount_inr=amount_inr,
            upi_id=upi_id,
            beneficiary_name=beneficiary_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            note=note,
        )

    def _t_get_investment_recommendations(self, goal: str = ""):
        return core_banking.get_investment_recommendations(self.customer_id, goal=goal)

    def _t_get_investment_portfolio(self):
        rows = core_banking.get_investments(self.customer_id)
        invested = sum(float(r.get("amount_inr") or 0) for r in rows)
        return {"success": True, "investments": rows, "total_invested_inr": round(invested, 2)}

    def _t_create_investment(self, product: str, amount_inr: float,
                             tenure_months=None, goal: str = ""):
        return core_banking.create_investment(
            self.customer_id, product, amount_inr,
            tenure_months=tenure_months, goal=goal)


def result_to_json(result: Dict[str, Any]) -> str:
    return json.dumps(result, default=str, ensure_ascii=False)
