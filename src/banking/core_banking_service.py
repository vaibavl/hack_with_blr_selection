from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import re
from ..synthetic_data.data_loader import get_customer_by_id, get_transactions_by_customer, get_all_policies

USD_INR_RATE = 94.11
NPCI_UPI_LIMIT = 100000.00        # ₹1,00,000 per UPI transaction (NPCI)
RTGS_MIN_AMOUNT = 200000.00       # ₹2,00,000 RTGS floor (RBI)
TRANSFER_MODES = ("UPI", "RTGS", "NEFT", "IMPS")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

# Chat-recommended investment catalogue the agent can place money into.
INVESTMENT_CATALOG: Dict[str, Dict[str, Any]] = {
    "fixed_deposit": {
        "product": "Apex 1-Yr Fixed Deposit", "category": "Fixed Deposit", "risk": "Very Low",
        "rate_pct": 6.85, "tenure_months": 12, "min_amount": 10000.00},
    "tax_saver_fd": {
        "product": "3-Yr Tax Saver Fixed Deposit (Sec 80C)", "category": "Fixed Deposit", "risk": "Very Low",
        "rate_pct": 7.65, "tenure_months": 36, "min_amount": 50000.00},
    "fixed_deposit_nre": {
        "product": "NRE Fixed Deposit (Tax-free in India)", "category": "Fixed Deposit", "risk": "Very Low",
        "rate_pct": 6.85, "tenure_months": 12, "min_amount": 10000.00},
    "recurring_deposit": {
        "product": "Apex Smart Recurring Deposit", "category": "Recurring Deposit", "risk": "Very Low",
        "rate_pct": 7.00, "tenure_months": 12, "min_amount": 5000.00},
    "liquid_fund": {
        "product": "Apex Liquid Mutual Fund (Sweep)", "category": "Mutual Fund", "risk": "Low",
        "rate_pct": 6.90, "tenure_months": 6, "min_amount": 10000.00},
    "corporate_bond": {
        "product": "Corporate Bond Fund", "category": "Mutual Fund", "risk": "Moderate",
        "rate_pct": 8.20, "tenure_months": 12, "min_amount": 25000.00},
    "index_sip": {
        "product": "Nifty 50 Index Fund SIP", "category": "Mutual Fund - Equity", "risk": "Moderate-High",
        "rate_pct": 12.00, "tenure_months": 36, "min_amount": 1000.00},
    "digital_gold": {
        "product": "Apex Digital Gold Saver", "category": "Digital Gold", "risk": "Moderate",
        "rate_pct": 9.50, "tenure_months": 12, "min_amount": 500.00},
    "usd_fixed_deposit": {
        "product": "USD Foreign-Currency Fixed Deposit (5.2% p.a.)", "category": "Forex Deposit", "risk": "Low",
        "rate_pct": 5.20, "tenure_months": 12, "min_amount": 1000.00},
}


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
        # Chat-driven ledger: money transfers executed via the conversational agent
        self.transactions_runtime: Dict[str, List[Dict[str, Any]]] = {}
        # Chat-driven investments booked via the conversational agent
        self.investments: Dict[str, List[Dict[str, Any]]] = {}
        self._txn_seq = 0
        self._inv_seq = 0

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

        # Prepend chat-driven transfers (newest first) so they surface immediately
        result[:0] = [dict(rt) for rt in reversed(self.transactions_runtime.get(customer_id, []))]

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
            self.account_balance_adjustments["ACC-SAV-77312"] = \
                self.account_balance_adjustments.get("ACC-SAV-77312", 0.0) + fee_amount_inr

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
            self.account_balance_adjustments["ACC-NRE-98214"] = \
                self.account_balance_adjustments.get("ACC-NRE-98214", 0.0) + 430000.0

        return {
            "success": True,
            "action": "FIRC_HOLD_RELEASED",
            "transaction_id": transaction_id,
            "purpose_code": purpose_code,
            "status": "FIRC Released - Funds Liquid",
            "message": f"Electronic FIRC purpose code [{purpose_code} - Software & IT Advisory] verified. Security hold on {transaction_id} ($5,000 USD / ₹4,30,000 INR) released; funds are now liquid in your NRE checking balance."
        }

    # ============================================================
    # Chat-driven money transfers (UPI / RTGS / NEFT / IMPS)
    # ============================================================
    def _liquid_inr_accounts(self, customer_id: str) -> List[Dict[str, Any]]:
        summary = self.get_account_summary(customer_id)
        return [a for a in summary.get("accounts", [])
                if a.get("currency", "INR") == "INR"
                and "fixed deposit" not in str(a.get("type", "")).lower()]

    def _pick_debit_account(self, customer_id: str, amount: float) -> Optional[Dict[str, Any]]:
        """Debit the INR savings/current account with the most available funds."""
        candidates = [a for a in self._liquid_inr_accounts(customer_id)
                      if a.get("available_balance", 0) >= amount]
        return max(candidates, key=lambda a: a["available_balance"], default=None)

    def execute_transfer(
        self,
        customer_id: str,
        mode: str,
        amount_inr: float,
        upi_id: str = None,
        beneficiary_name: str = None,
        account_number: str = None,
        ifsc_code: str = None,
        note: str = None,
    ) -> Dict[str, Any]:
        mode = (mode or "UPI").upper().strip()
        if mode not in TRANSFER_MODES:
            return {"success": False,
                    "error": f"Unsupported transfer mode '{mode}'. Supported: UPI, RTGS, NEFT, IMPS."}

        try:
            amount = round(float(amount_inr), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "Transfer amount must be a number in INR."}
        if amount <= 0:
            return {"success": False, "error": "Transfer amount must be greater than ₹0."}

        # Mode-specific required fields and limits
        missing: List[str] = []
        if mode == "UPI":
            upi_id = (upi_id or "").strip()
            if not upi_id:
                missing.append("receiver's UPI ID (e.g. name@bank)")
            elif not re.match(r"^[A-Za-z0-9.\-_]{2,}@[A-Za-z]{2,}$", upi_id):
                return {"success": False, "error": f"'{upi_id}' does not look like a valid UPI ID. It should look like name@bank (e.g. ramesh@okhdfc)."}
            if amount > NPCI_UPI_LIMIT:
                return {"success": False,
                        "error": f"UPI per-transaction limit is ₹1,00,000 (NPCI). Please use RTGS/NEFT for {amount:,.2f}.",
                        "recommended_mode": "RTGS" if amount >= RTGS_MIN_AMOUNT else "NEFT"}
        else:
            beneficiary_name = (beneficiary_name or "").strip()
            account_number = str(account_number or "").strip()
            ifsc_code = (ifsc_code or "").strip().upper()
            if not beneficiary_name:
                missing.append("beneficiary's full name")
            if not account_number:
                missing.append("beneficiary's account number")
            if not ifsc_code:
                missing.append("beneficiary bank's IFSC code")
            elif not IFSC_RE.match(ifsc_code):
                return {"success": False,
                        "error": f"'{ifsc_code}' is not a valid IFSC code (format: 4 letters + 0 + 6 alphanumerics, e.g. HDFC0000123)."}
            if mode == "RTGS" and amount < RTGS_MIN_AMOUNT:
                return {"success": False,
                        "error": f"RTGS minimum is ₹2,00,000 (RBI). For this amount, IMPS or NEFT is the right rail.",
                        "recommended_mode": "IMPS"}

        if missing:
            return {"success": False, "action": "TRANSFER_INFO_REQUIRED", "mode": mode,
                    "missing_fields": missing,
                    "error": f"For {mode} I still need: {', '.join(missing)}."}

        cust = get_customer_by_id(customer_id)
        if not cust:
            return {"success": False, "error": "Customer account not found"}
        debit_acc = self._pick_debit_account(customer_id, amount)
        if not debit_acc:
            return {"success": False,
                    "error": f"Insufficient liquid funds for {amount:,.2f}. No INR account covers this transfer."}

        # Ledger mutation: deduct from the chosen account
        acc_id = debit_acc["account_id"]
        self.account_balance_adjustments[acc_id] = \
            self.account_balance_adjustments.get(acc_id, 0.0) - amount

        # Build the settlement record visible in Recent Activities
        now = datetime.now(timezone.utc)
        self._txn_seq += 1
        utr = f"{mode[:4]}{now.strftime('%d%m%H%M%S')}{self._txn_seq:04d}"
        if mode == "UPI":
            description = f"UPI Transfer to {upi_id}" + (f" ({note[:40]})" if note else "")
            category = "UPI P2P Transfer"
            payment_mode = "NPCI UPI"
            status = "Settled - NPCI UPI Network"
        else:
            masked = ("••••• " + account_number[-4:]) if len(account_number) > 4 else account_number
            description = (f"{mode} Transfer to {beneficiary_name} "
                           f"({masked} / {ifsc_code})" + (f" — {note[:40]}" if note else ""))
            category = f"{mode} Beneficiary Payment"
            payment_mode = mode
            status = {"RTGS": "Settled - RTGS Real-time Gross",
                      "NEFT": "Settled - NEFT Batch T+0",
                      "IMPS": "Settled - IMPS Immediate"}.get(mode, "Settled")

        txn = {
            "transaction_id": f"TXN-CHAT-{now.strftime('%y%m%d')}-{self._txn_seq:04d}",
            "customer_id": customer_id,
            "account_id": acc_id,
            "date": now.isoformat(),
            "description": description,
            "category": category,
            "amount_inr": -amount,
            "amount_usd": round(-amount / USD_INR_RATE, 2),
            "currency": "INR",
            "status": status,
            "payment_mode": payment_mode,
            "utr_ref": utr,
            "disputable": True,
        }
        self.transactions_runtime.setdefault(customer_id, []).append(txn)

        new_balance = round(debit_acc["available_balance"] - amount, 2)
        if mode == "UPI":
            to_label = f"UPI ID {upi_id}"
        else:
            to_label = f"{beneficiary_name} • a/c {masked} • IFSC {ifsc_code}"
        return {
            "success": True,
            "action": "MONEY_TRANSFERRED",
            "mode": mode,
            "amount_inr": amount,
            "receiver": to_label,
            "transaction_id": txn["transaction_id"],
            "utr_ref": utr,
            "status": status,
            "payment_mode": payment_mode,
            "debited_account_id": acc_id,
            "new_account_balance_inr": new_balance,
            "timestamp": txn["date"],
            "message": (f"{mode} transfer of ₹{amount:,.2f} to {to_label} completed successfully "
                        f"({txn['transaction_id']}, UTR {utr}). Account {acc_id} balance is now ₹{new_balance:,.2f}.")
        }

    # ============================================================
    # Chat-driven investments & savings
    # ============================================================
    def _investable_surplus(self, customer_id: str) -> float:
        return sum(a.get("available_balance", 0.0) for a in self._liquid_inr_accounts(customer_id))

    @staticmethod
    def _resolve_product_key(product: str) -> Optional[str]:
        p = (product or "").lower()
        if "tax saver" in p or "80c" in p:
            return "tax_saver_fd"
        if "nre" in p and "fd" in p:
            return "fixed_deposit_nre"
        if "fixed deposit" in p or "fd" in p:
            return "fixed_deposit"
        if "recurring" in p or "rd" == p.strip():
            return "recurring_deposit"
        if "liquid" in p or "overnight" in p or "money market" in p:
            return "liquid_fund"
        if "bond" in p:
            return "corporate_bond"
        if "index" in p or "nifty" in p or "sip" in p or "equity" in p or "mutual" in p or "fund" in p:
            return "index_sip"
        if "gold" in p:
            return "digital_gold"
        if "usd" in p or "forex" in p or "foreign" in p:
            return "usd_fixed_deposit"
        return None

    def get_investment_recommendations(self, customer_id: str, goal: str = "") -> Dict[str, Any]:
        """Rule-based, tier-aware shortlist drawn from the bank's own product catalogue."""
        summary = self.get_account_summary(customer_id)
        tier = summary.get("tier", "")
        surplus = self._investable_surplus(customer_id)

        recs: List[Dict[str, Any]] = []
        universal = ["fixed_deposit", "liquid_fund", "index_sip", "tax_saver_fd"]
        if "Premier" in tier or "NRI" in tier:
            picks = ["fixed_deposit_nre", "usd_fixed_deposit", "corporate_bond", "index_sip"]
        elif "Vyapar" in tier or "MSME" in tier:
            picks = ["liquid_fund", "fixed_deposit", "recurring_deposit", "tax_saver_fd"]
        else:
            picks = ["index_sip", "recurring_deposit", "fixed_deposit", "liquid_fund"]

        for key in picks + [k for k in universal if k not in picks]:
            if len(recs) >= 4:
                break
            p = INVESTMENT_CATALOG[key]
            recs.append({
                "product_key": key,
                "product": p["product"],
                "category": p["category"],
                "risk": p["risk"],
                "indicative_rate_pct": p["rate_pct"],
                "suggested_horizon_months": p["tenure_months"],
                "min_amount_inr": p["min_amount"],
                "suitable_for": (f"goal '{goal}'" if goal else "your stated goal"),
                "why": self._why(key, tier),
            })

        return {
            "success": True,
            "action": "INVESTMENT_RECOMMENDATIONS",
            "customer_tier": tier,
            "investable_surplus_inr": round(surplus, 2),
            "recommendations": recs,
            "disclaimer": ("Indicative returns, not guaranteed (equity funds are market-linked). "
                           "Demo advisory — no SEBI-registered advice implied."),
            "message": (f"{len(recs)} recommendations prepared based on your {tier} profile and "
                        f"investable surplus of ₹{surplus:,.2f}. Ask me to invest in any one of them.")
        }

    @staticmethod
    def _why(key: str, tier: str) -> str:
        reasons = {
            "fixed_deposit": "RBI-rate-backed certainty; good parking for idle savings at 6.85% p.a.",
            "tax_saver_fd": "Section 80C deduction up to ₹1,50,000 with a 7.65% p.a. lock-in product.",
            "fixed_deposit_nre": "Tax-free interest in India for your NRE status; fully repatriable.",
            "recurring_deposit": "Automated monthly habit — bundles discipline with FD-grade safety.",
            "liquid_fund": "Sweep-friendly parking for surplus; T+1 liquidity for working capital.",
            "corporate_bond": "Step above FD yields from AAA-rated issuers, moderate interest-rate risk.",
            "index_sip": "Rupee-cost averaging into the broad market; best for 3-year-plus horizons.",
            "digital_gold": "Inflation hedge that stays 100% liquid as a nominated gold balance.",
            "usd_fixed_deposit": "Keeps reserve dollars earning 5.2% without converting back to INR.",
        }
        base = reasons.get(key, "Diversified parking option consistent with your profile.")
        if "MSME" in tier and key in ("liquid_fund", "recurring_deposit"):
            return base + " Fits your Monday supplier-payout cycle after Soundbox settlements."
        if "Youth" in tier and key == "index_sip":
            return base + " Long your 30-year earning runway — SIP starting from just ₹1,000."
        return base

    def create_investment(
        self,
        customer_id: str,
        product: str,
        amount_inr: float,
        tenure_months: Optional[int] = None,
        goal: str = "",
    ) -> Dict[str, Any]:
        key = self._resolve_product_key(product)
        if not key:
            return {"success": False,
                    "error": ("I couldn't match that to a product. Options: Fixed Deposit, Tax Saver FD, "
                              "NRE Fixed Deposit, Recurring Deposit, Liquid Fund, Corporate Bond Fund, "
                              "Nifty 50 Index SIP, Digital Gold, USD Fixed Deposit.")}
        spec = INVESTMENT_CATALOG[key]
        try:
            amount = round(float(amount_inr), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "Investment amount must be a number in INR."}

        if amount <= 0:
            return {"success": False, "error": "Investment amount must be greater than ₹0."}
        if amount < spec["min_amount"]:
            return {"success": False,
                    "error": (f"{spec['product']} requires a minimum of ₹{spec['min_amount']:,.2f}. "
                              f"Alternatively pick a product with a lower entry point.")}
        surplus = self._investable_surplus(customer_id)
        if amount > surplus:
            return {"success": False,
                    "error": (f"Insufficient liquid funds for ₹{amount:,.2f}. "
                              f"Your investable surplus (excluding locked FDs) is ₹{surplus:,.2f}.")}

        source = self._pick_debit_account(customer_id, amount)
        if not source:
            return {"success": False, "error": "No liquid INR account can fund this investment."}

        # Deduct the invested principal from the source account
        acc_id = source["account_id"]
        self.account_balance_adjustments[acc_id] = \
            self.account_balance_adjustments.get(acc_id, 0.0) - amount

        tenor = int(tenure_months) if tenure_months else spec["tenure_months"]
        if key in ("index_sip", "liquid_fund", "corporate_bond", "digital_gold"):
            # Market-linked: indicative projection, simple annualised approximation
            maturity_value = round(amount * (1 + spec["rate_pct"] / 100 * tenor / 12), 2)
            is_projected = True
        else:
            maturity_value = round(amount * (1 + spec["rate_pct"] / 100 * tenor / 12), 2)
            is_projected = False

        now = datetime.now(timezone.utc)
        self._inv_seq += 1
        inv = {
            "investment_id": f"INV-{now.strftime('%Y')}-{self._inv_seq:04d}",
            "customer_id": customer_id,
            "product": spec["product"],
            "category": spec["category"],
            "risk": spec["risk"],
            "amount_inr": amount,
            "rate_pct": spec["rate_pct"],
            "tenure_months": tenor,
            "start_date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "maturity_date": (now + timedelta(days=tenor * 30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expected_maturity_value_inr": maturity_value,
            "returns_projected": is_projected,
            "source_account_id": acc_id,
            "status": "Active",
        }
        self.investments.setdefault(customer_id, []).append(inv)

        return {
            "success": True,
            "action": "INVESTMENT_CREATED",
            "investment_id": inv["investment_id"],
            "product": inv["product"],
            "amount_inr": amount,
            "rate_pct": inv["rate_pct"],
            "tenure_months": tenor,
            "maturity_date": inv["maturity_date"],
            "expected_maturity_value_inr": maturity_value,
            "debited_account_id": acc_id,
            "message": (f"{inv['product']} booked for ₹{amount:,.2f} ({inv['rate_pct']}% p.a., "
                        f"{tenor} months). It now appears in your Investments & Savings tab. "
                        f"Account {acc_id} balance updated accordingly.")
        }

    def get_investments(self, customer_id: str) -> List[Dict[str, Any]]:
        """Runtime chat-booked investments + the customer's non-chat, standing FD accounts."""
        rows: List[Dict[str, Any]] = []
        summary = self.get_account_summary(customer_id)
        for a in summary.get("accounts", []):
            if "fixed deposit" in str(a.get("type", "")).lower():
                hist_standing = {
                    "investment_id": a["account_id"],
                    "customer_id": customer_id,
                    "product": a["type"],
                    "category": "Fixed Deposit",
                    "risk": "Very Low",
                    "amount_inr": a.get("balance_inr", a.get("balance", 0.0)),
                    "rate_pct": None,
                    "tenure_months": None,
                    "start_date": None,
                    "maturity_date": None,
                    "expected_maturity_value_inr": None,
                    "source_account_id": a["account_id"],
                    "status": "Active",
                }
                rows.append(hist_standing)
        rows.extend(self.investments.get(customer_id, []))
        return rows

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
