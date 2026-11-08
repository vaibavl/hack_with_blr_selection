import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.banking.core_banking_service import core_banking
from src.banking.compliance import BankingComplianceGuard

class TestCoreBankingService(unittest.TestCase):

    def test_compliance_masking(self):
        raw_text = "My Aadhaar is 5544 3322 1100, PAN is ABCDE1234F, card is 4111-2222-3333-4481 and UPI PIN: 9021"
        sanitized = BankingComplianceGuard.sanitize_user_input(raw_text)
        self.assertNotIn("4111-2222-3333", sanitized)
        self.assertIn("****-****-****-4481", sanitized)
        self.assertNotIn("5544 3322 1100", sanitized)
        self.assertIn("AADHAAR MASKED", sanitized)
        self.assertNotIn("9021", sanitized)

    def test_fee_waiver_policy(self):
        # Priya (CUST-IN-103) has 0 prior waivers -> eligible
        priya_elig = core_banking.check_fee_waiver_eligibility("CUST-IN-103")
        self.assertTrue(priya_elig["eligible"])

        # Rajesh (CUST-IN-102) has 1 prior courtesy waiver -> requires escalation per POL-RBI-FEE-001
        rajesh_elig = core_banking.check_fee_waiver_eligibility("CUST-IN-102")
        self.assertFalse(rajesh_elig["eligible"])
        self.assertTrue(rajesh_elig["requires_escalation"])

    def test_freeze_and_unfreeze_card(self):
        freeze_res = core_banking.freeze_card("CUST-IN-101", "CARD-METAL-4481")
        self.assertTrue(freeze_res["success"])
        self.assertEqual(freeze_res["status"], "Frozen - Protection Active")

        unfreeze_res = core_banking.unfreeze_card("CUST-IN-101", "CARD-METAL-4481")
        self.assertTrue(unfreeze_res["success"])
        self.assertEqual(unfreeze_res["status"], "Active")

    def test_currency_conversion(self):
        conv = core_banking.convert_currency(100.0, "USD", "INR")
        self.assertEqual(conv["converted_amount"], 8650.00)

if __name__ == "__main__":
    unittest.main()
