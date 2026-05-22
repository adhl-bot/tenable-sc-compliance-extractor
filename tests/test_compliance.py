import unittest

from tenable_sc_phase1.compliance import build_summary_row, filter_assets


class ComplianceSummaryTests(unittest.TestCase):
    def test_build_summary_row_maps_info_to_passed_and_other_severities_to_failed(self):
        row = build_summary_row(
            {"id": "1", "name": "Linux Hosts", "type": "dynamic", "ipCount": 12},
            {
                "id": "1000010",
                "name": "Example Audit",
                "filename": "scfile_example",
                "type": "unix",
            },
            [
                {"severity": {"id": "0"}, "count": "8"},
                {"severity": {"id": "1"}, "count": "1"},
                {"severity": {"id": "2"}, "count": "2"},
                {"severity": {"id": "3"}, "count": "3"},
                {"severity": {"id": "4"}, "count": "4"},
            ],
        )

        self.assertEqual(row.passed_controls, 8)
        self.assertEqual(row.failed_controls, 10)
        self.assertEqual(row.total_controls, 18)
        self.assertEqual(row.compliance_percent, 44.44)

    def test_filter_assets_keeps_explicit_zero_ip_asset(self):
        assets = [
            {"id": "0", "name": "All Defined Ranges", "ipCount": 0},
            {"id": "1", "name": "Linux Hosts", "ipCount": 4},
        ]

        selected = filter_assets(assets, asset_ids=[0])

        self.assertEqual([asset["id"] for asset in selected], ["0"])


if __name__ == "__main__":
    unittest.main()

