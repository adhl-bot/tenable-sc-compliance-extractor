import unittest

from laboratorio.build_lab import INCIDENT_CATALOG, analysis_payload, summarize_resource, supervisor_ok


class LabBuildTests(unittest.TestCase):
    def test_incident_catalog_keeps_expected_repair_cases(self):
        expected = {
            "tenablesc_postgres_down": "postgres",
            "tenablesc_asset_artifacts_missing": "assets",
            "tenablesc_analysis_asset_filter_bad": "assets",
            "tenablesc_scan_import_errors": "inspect",
        }

        for code, repair in expected.items():
            self.assertIn(code, INCIDENT_CATALOG)
            self.assertEqual(INCIDENT_CATALOG[code]["repair"], repair)

    def test_supervisor_ok_requires_apache_and_jobd(self):
        self.assertTrue(
            supervisor_ok(
                "TenableSC:Apache                 RUNNING   pid 1\n"
                "TenableSC:Jobd                   RUNNING   pid 2\n"
            )
        )
        self.assertFalse(supervisor_ok("TenableSC:Apache                 RUNNING   pid 1\n"))

    def test_analysis_payload_uses_cumulative_compliance_asset_filter(self):
        payload = analysis_payload(118, tool="vulndetails", end_offset=50)
        filters = payload["query"]["filters"]

        self.assertEqual(payload["type"], "vuln")
        self.assertEqual(payload["sourceType"], "cumulative")
        self.assertEqual(payload["query"]["tool"], "vulndetails")
        self.assertIn({"filterName": "pluginType", "operator": "=", "value": "compliance"}, filters)
        self.assertIn({"filterName": "assetID", "operator": "=", "value": "118"}, filters)

    def test_summarize_resource_counts_usable_and_manageable_samples(self):
        summary = summarize_resource(
            {
                "response": {
                    "usable": [{"id": "1"}, {"id": "2"}],
                    "manageable": [{"id": "1"}],
                }
            }
        )

        self.assertEqual(summary["usable_count"], 2)
        self.assertEqual(summary["usable_sample"], [{"id": "1"}, {"id": "2"}])
        self.assertEqual(summary["manageable_count"], 1)


if __name__ == "__main__":
    unittest.main()
