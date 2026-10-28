"""Tests for the FinOps cost analyzer (stdlib unittest, no dependencies)."""
import os
import tempfile
import unittest

import analyze
import generate_data


class TestAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.csv = os.path.join(cls.tmp, "billing.csv")
        cls.md = os.path.join(cls.tmp, "report.md")
        generate_data.main(cls.csv)
        analyze.main(cls.csv, cls.md)
        with open(cls.md) as f:
            cls.report = f.read()

    def test_report_has_all_sections(self):
        for heading in ["Spend by provider", "Cost allocation by team", "Cost anomalies",
                        "Rate optimization", "Idle and rightsizing", "AI / LLM cost"]:
            self.assertIn(heading, self.report)

    def test_detects_all_three_bedrock_spike_days(self):
        for day in ["2026-08-31", "2026-09-01", "2026-09-02"]:
            self.assertRegex(self.report, rf"\| {day} \| Amazon Bedrock \|")

    def test_no_false_anomalies_on_other_services(self):
        anomaly_rows = [l for l in self.report.splitlines() if "runaway agent" in l or "usage increase" in l]
        self.assertTrue(all("Amazon Bedrock" in l for l in anomaly_rows))

    def test_untagged_spend_surfaced(self):
        self.assertIn("(untagged)", self.report)
        self.assertIn("Tagging coverage", self.report)

    def test_idle_resources_flagged(self):
        for rid in ["i-old-test", "i-staging-01", "vol-orphan-7"]:
            self.assertIn(rid, self.report)
        self.assertNotIn("| i-api-01 |", self.report)  # busy prod box must not be flagged

    def test_rate_metrics_formulas(self):
        # coverage = covered / eligible; net = covered - fee; ESR = net / eligible
        covered, eligible, fee = 8000.0, 10000.0, 5000.0
        net = covered - fee
        self.assertAlmostEqual(100 * covered / eligible, 80.0)
        self.assertAlmostEqual(100 * net / eligible, 30.0)
        for metric in ["Coverage %", "Utilization %", "Net savings $", "Effective savings rate (ESR) %"]:
            self.assertIn(metric, self.report)


if __name__ == "__main__":
    unittest.main()
