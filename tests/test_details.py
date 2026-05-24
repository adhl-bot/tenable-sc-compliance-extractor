import unittest

from tenable_sc_phase1.details import (
    compliance_tag,
    compliance_tag_values,
    ip_sort_key,
    normalize_detail_record,
)


class DetailExtractionTests(unittest.TestCase):
    def test_compliance_tag_prefers_first_non_empty_value(self):
        plugin_text = (
            "<cm:compliance-actual-value></cm:compliance-actual-value>"
            "<cm:compliance-actual-value>root:root</cm:compliance-actual-value>"
        )

        self.assertEqual(
            compliance_tag(plugin_text, "compliance-actual-value"),
            "root:root",
        )

    def test_normalize_detail_record_maps_minimum_fields(self):
        row = normalize_detail_record(
            {"name": "compliance_example"},
            {
                "ip": "192.168.128.30",
                "pluginName": "Fallback control",
                "lastSeen": "1762463181",
                "pluginText": (
                    "<cm:compliance-check-name>Example control</cm:compliance-check-name>"
                    "<cm:compliance-actual-value>enabled</cm:compliance-actual-value>"
                ),
            },
        )

        self.assertEqual(row["asset"], "compliance_example")
        self.assertEqual(row["ip"], "192.168.128.30")
        self.assertEqual(row["control_name"], "Example control")
        self.assertEqual(row["actual_value"], "enabled")
        self.assertEqual(row["actual_values"], ["enabled"])
        self.assertEqual(row["last_observed"], "2025-11-06T21:06:21Z")

    def test_normalize_detail_record_preserves_grouped_duplicate_results(self):
        plugin_text = (
            "<cm:compliance-check-name>Duplicated control</cm:compliance-check-name>"
            "<cm:compliance-result>PASSED</cm:compliance-result>"
            "<cm:compliance-actual-value>0</cm:compliance-actual-value>"
            "<cm:compliance-result>FAILED</cm:compliance-result>"
            "<cm:compliance-actual-value>1</cm:compliance-actual-value>"
        )

        row = normalize_detail_record(
            {"name": "compliance_example"},
            {
                "ip": "192.168.1.138",
                "pluginID": "1000200",
                "vulnUUID": "example-vuln-uuid",
                "lastSeen": "1779569492",
                "pluginText": plugin_text,
            },
        )

        self.assertEqual(row["plugin_id"], "1000200")
        self.assertEqual(row["vuln_uuid"], "example-vuln-uuid")
        self.assertEqual(row["compliance_results"], ["PASSED", "FAILED"])
        self.assertEqual(row["actual_values"], ["0", "1"])
        self.assertEqual(row["actual_value"], "0")

    def test_compliance_tag_values_returns_all_matches(self):
        plugin_text = (
            "<cm:compliance-result>PASSED</cm:compliance-result>"
            "<cm:compliance-result>FAILED</cm:compliance-result>"
        )

        self.assertEqual(
            compliance_tag_values(plugin_text, "compliance-result"),
            ["PASSED", "FAILED"],
        )

    def test_ip_sort_key_orders_ipv4_numerically(self):
        ips = ["192.168.128.30", "10.0.0.2", "10.0.0.10"]

        self.assertEqual(sorted(ips, key=ip_sort_key), ["10.0.0.2", "10.0.0.10", "192.168.128.30"])


if __name__ == "__main__":
    unittest.main()
