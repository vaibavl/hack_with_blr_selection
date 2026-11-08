from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from ..synthetic_data.data_loader import get_customer_by_id, get_transactions_by_customer, get_all_policies

USD_INR_RATE = 94.11

class CoreBankingService:
    """
    Enterprise Indian & Cross-Border Core Banking & Ledger API.
    Handles dual-currency accounts (INR ₹ & USD $), real-time balance mutations,
    UPI settlements, card locks, fee waivers, FIRC inward wire hold releases, and chargebacks.
    """

    def __init__(self):
        self.card_overrides: Dict[str, str] = {}
        self.disputes: List[Dict[str, Any]] = []
        self.waiver_history: Dict[str, List[Dict[str, Any]]] = {
            "CUST-IN-102": [
                {
                    "date": "2026-10-05T10:20:00Z",
                    "amount_inr": 350.00,
                    "type": "NACH Mandate Return Fee",
                    "status": "Approved One-Time Courtesy per RBI Circular"
                }
            ]
        }
        self.travel_notices: List[Dict[str, Any]] = []
        self.wire_clearances: Dict[str, str] = {}
        # Runtime balance modifications (e.g. holds released, waivers credited)
        self.account_hold_overrides: Dict[str, float] = {}
        self.account_balance_adjustments: Dict[str, float] = {}

    def get_account_summary(self, customer_id: str) -> Dict[str, Any]:
        cust = get_customer_by_id(customer_id)
        if not cust:
            return {"error": "Customer not found"}

        policies = get_all_policies()
        fx_rate = policies.get("fx_rate_usd_to_inr", USD_INR_RATE)

        enriched_accounts = []
        total_inr = 0.0
        total_usd = 0.0

        for acc in cust.get("accounts", []):
            acc_copy = dict(acc)
            acc_id = acc_copy["account_id"]
            
            # Apply runtime hold overrides and balance adjustments
            if acc_id in self.account_hold_overrides:
                acc_copy["hold_amount"] = self.account_hold_overrides[acc_id]
                if acc_copy["hold_amount"] == 0:
                    acc_copy["hold_reason"] = "All security holds resolved"

            if acc_id in self.account_balance_adjustments:
                acc_copy["available_balance"] += self.account_balance_adjustments[acc_id]
                acc_copy["balance"] += self.account_balance_adjustments[acc_id]

            bal = acc_copy["available_balance"]
            curr = acc_copy["currency"]

            if curr == "INR":
                acc_copy["balance_inr"] = bal
                acc_copy["balance_usd"] = round(bal / fx_rate, 2)
                total_inr += bal
                total_usd += bal / fx_rate
            else:
                acc_copy["balance_usd"] = bal
                acc_copy["balance_inr"] = round(bal * fx_rate, 2)
                total_usd += bal
                total_inr += bal * fx_rate

            enriched_accounts.append(acc_copy)

        # Apply card status overrides
        cards = []
        for c in cust.get("cards", []):
            card_copy = dict(c)
            if c["card_id"] in self.card_overrides:
                card_copy["status"] = self.card_overrides[c["card_id"]]
            cards.append(card_copy)

        return {
            "customer_id": cust["id"],
            "name": cust["name"],
            "tier": cust["tier"],
            "city": cust.get("city", "Hyderabad"),
            "kyc_status": cust["kyc_status"],
            "upi_id": cust.get("upi_id", "N/A"),
            "accounts": enriched_accounts,
            "total_liquid_inr": round(total_inr, 2),
            "total_liquid_usd": round(total_usd, 2),
            "cards": cards,
            "risk_score": cust["risk_score"],
            "branch": "MG Road Corporate Branch, Bengaluru",
            "ifsc": policies.get("ifsc_code", "APEX0004921"),
            "fx_rate": fx_rate
        }

    def get_transactions(self, customer_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        txns = get_transactions_by_customer(customer_id)
        result = []
        for t in txns:
            t_copy = dict(t)
            if t["transaction_id"] in self.wire_clearances:
                t_copy["status"] = self.wire_clearances[t["transaction_id"]]
            result.append(t_copy)

        # Prepend runtime disputes
        for d in self.disputes:
            if d["customer_id"] == customer_id:
                result.insert(0, {
                    "transaction_id": d["dispute_id"],
                    "customer_id": customer_id,
                    "account_id": "ACC-DISPUTE",
                    "date": d["date_filed"],
                    "description": f"Provisional Credit: {d['reason'][:30]}...",
                    "category": "Grievance Adjustment",
                    "amount_inr": 899.00,
                    "amount_usd": 10.39,
                    "currency": "INR",
                    "status": "Provisional Credit Posted",
                    "payment_mode": "RBI Grievance Reversal",
                    "utr_ref": f"REV{d['dispute_id'][-6:]}",
                    "disputable": False
                })

        return result[:limit]

    def freeze_card(self, customer_id: str, card_id: str, reason: str = "Customer security request") -> Dict[str, Any]:
        cust = get_customer_by_id(customer_id)
        if not cust:
            return {"success": False, "message": "Customer account not found"}

        self.card_overrides[card_id] = "Frozen - Protection Active"
        return {
            "success": True,
            "action": "FREEZE_CARD",
            "card_id": card_id,
            "status": "Frozen - Protection Active",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Card {card_id} has been blocked immediately per RBI electronic security protocol. Pre-scheduled UPI AutoPay remains active, but all new ATM/POS/E-Com authorizations are blocked."
        }

    def unfreeze_card(self, customer_id: str, card_id: str) -> Dict[str, Any]:
        self.card_overrides[card_id] = "Active"
        return {
            "success": True,
            "action": "UNFREEZE_CARD",
            "card_id": card_id,
            "status": "Active",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Card {card_id} has been successfully reactivated and unblocked. Contactless tap-to-pay, chip, and online payments are active."
        }

    def check_fee_waiver_eligibility(self, customer_id: str) -> Dict[str, Any]:
        cust = get_customer_by_id(customer_id)
        if not cust:
            return {"eligible": False, "reason": "Customer record not found"}

        past_waivers = self.waiver_history.get(customer_id, [])
        if past_waivers:
            last = past_waivers[-1]
            return {
                "eligible": False,
                "customer_tier": cust["tier"],
                "reason": f"A prior courtesy fee reversal (₹{last['amount_inr']} on {last['date'][:10]}) was already granted within the 12-month rolling period. Policy POL-RBI-FEE-001 requires Regional Branch Manager sign-off.",
                "requires_escalation": True,
                "past_waiver_count": len(past_waivers)
            }

        return {
            "eligible": True,
            "customer_tier": cust["tier"],
            "reason": "Account maintains high CIBIL and clean standing with zero penalty reversals in the past 12 months. Eligible for automated courtesy credit.",
            "requires_escalation": False,
            "past_waiver_count": 0
        }

    def process_fee_waiver(self, customer_id: str, fee_amount_inr: float, reason: str) -> Dict[str, Any]:
        eligibility = self.check_fee_waiver_eligibility(customer_id)
        if not eligibility["eligible"]:
            return {
                "success": False,
                "message": eligibility["reason"],
                "requires_escalation": True
            }

        record = {
            "date": datetime.now(timezone.utc).isoformat(),
            "amount_inr": fee_amount_inr,
            "type": "Courtesy Reversal",
            "status": "Approved - Credited to Savings",
            "reason": reason
        }
        if customer_id not in self.waiver_history:
            self.waiver_history[customer_id] = []
        self.waiver_history[customer_id].append(record)

        # Apply real-time balance mutation: release hold and increase available balance
        if customer_id == "CUST-IN-103":
            self.account_hold_overrides["ACC-SAV-77312"] = 0.0
            self.account_balance_adjustments["ACC-SAV-77312"] = fee_amount_inr

        return {
            "success": True,
            "action": "CREDIT_FEE_WAIVER",
            "amount_credited_inr": fee_amount_inr,
            "timestamp": record["date"],
            "message": f"Courtesy reversal of ₹{fee_amount_inr:.2f} has been approved and credited back to your account balance. Hold released."
        }

    def initiate_dispute(self, customer_id: str, transaction_id: str, reason: str) -> Dict[str, Any]:
        cust = get_customer_by_id(customer_id)
        tier = cust.get("tier", "") if cust else ""
        provisional_hrs = "24 hours (Zero Liability SLA)" if "Premier" in tier else "48 hours (RBI Charter)"

        dispute_record = {
            "dispute_id": f"DSP-RBI-{len(self.disputes) + 7041}",
            "customer_id": customer_id,
            "transaction_id": transaction_id,
            "reason": reason,
            "date_filed": datetime.now(timezone.utc).isoformat(),
            "status": "Provisional Credit Posted per RBI Grievance Policy",
            "timeline": provisional_hrs
        }
        self.disputes.append(dispute_record)

        return {
            "success": True,
            "dispute_id": dispute_record["dispute_id"],
            "status": dispute_record["status"],
            "timeline": provisional_hrs,
            "message": f"Formal dispute grievance {dispute_record['dispute_id']} registered for {transaction_id}. Per RBI Customer Protection Charter, provisional credit will be credited within {provisional_hrs}."
        }

    def expedite_firc_wire_hold(self, customer_id: str, transaction_id: str, purpose_code: str = "P0802") -> Dict[str, Any]:
        self.wire_clearances[transaction_id] = "FIRC Released - Funds Liquid"
        # Mutate account hold: remove hold and credit funds to available balance
        if customer_id == "CUST-IN-101":
            self.account_hold_overrides["ACC-NRE-98214"] = 0.0
            self.account_balance_adjustments["ACC-NRE-98214"] = 430000.0

        return {
            "success": True,
            "action": "FIRC_HOLD_RELEASED",
            "transaction_id": transaction_id,
            "purpose_code": purpose_code,
            "status": "FIRC Released - Funds Liquid",
            "message": f"Electronic FIRC purpose code [{purpose_code} - Software & IT Advisory] verified. Security hold on {transaction_id} ($5,000 USD / ₹4,30,000 INR) released; funds are now liquid in your NRE checking balance."
        }

    def convert_currency(self, amount: float, from_curr: str = "USD", to_curr: str = "INR") -> Dict[str, Any]:
        fx_rate = USD_INR_RATE
        if from_curr.upper() == "USD" and to_curr.upper() == "INR":
            converted = amount * fx_rate
            return {
                "input_amount": amount,
                "from_currency": "USD",
                "to_currency": "INR",
                "exchange_rate": fx_rate,
                "converted_amount": round(converted, 2),
                "formatted": f"${amount:,.2f} USD = ₹{converted:,.2f} INR (Zero Markup Interbank Rate @ {fx_rate})"
            }
        elif from_curr.upper() == "INR" and to_curr.upper() == "USD":
            converted = amount / fx_rate
            return {
                "input_amount": amount,
                "from_currency": "INR",
                "to_currency": "USD",
                "exchange_rate": fx_rate,
                "converted_amount": round(converted, 2),
                "formatted": f"₹{amount:,.2f} INR = ${converted:,.2f} USD (Rate: ₹{fx_rate}/USD)"
            }
        return {"error": "Unsupported currency pair"}

core_banking = CoreBankingService()
