import unittest

from laboratorio.tenablesc_internals.inspect_tenablesc_internals import (
    parse_asset_counts,
    redact_text,
    summarize_asset_files,
    summarize_repository_files,
)


class TenableScInternalsTests(unittest.TestCase):
    def test_redact_text_masks_common_secret_patterns(self):
        raw = "accesskey=abc; secretkey=def; password: hunter2 token=xyz"
        redacted = redact_text(raw)

        self.assertNotIn("abc", redacted)
        self.assertNotIn("def", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("xyz", redacted)
        self.assertIn("<redacted>", redacted)

    def test_summarize_asset_files_counts_suffixes_and_zero_bytes(self):
        stdout = "\n".join(
            [
                "118.ip|15|/opt/sc/orgs/1/assets/0/10/118.ip",
                "118.uuidd|0|/opt/sc/orgs/1/assets/0/10/118.uuidd",
                "all.uuidd|120|/opt/sc/orgs/1/assets/0/10/all.uuidd",
            ]
        )

        summary = summarize_asset_files(stdout)

        self.assertEqual(summary["total_files"], 3)
        self.assertEqual(summary["by_suffix"][".uuidd"], 2)
        self.assertEqual(summary["zero_byte_by_suffix"][".uuidd"], 1)

    def test_summarize_repository_files_extracts_repo_and_key_files(self):
        stdout = "\n".join(
            [
                "/opt/sc/repositories/9/hdb.db|8472412",
                "/opt/sc/repositories/9/hdb.raw|219327916",
                "/opt/sc/repositories/10/vulns.db|61440",
            ]
        )

        summary = summarize_repository_files(stdout)

        self.assertEqual(summary["total_files"], 3)
        self.assertEqual(summary["repositories"]["9"]["files"], 2)
        self.assertEqual(summary["repositories"]["9"]["key_files"]["hdb.db"], 8472412)
        self.assertEqual(summary["repositories"]["10"]["key_files"]["vulns.db"], 61440)

    def test_parse_asset_counts_uses_complete_awk_summary(self):
        stdout = "total_files|10\nsuffix|.uuidd|4|2\nsuffix|.ip|6|1"

        summary = parse_asset_counts(stdout)

        self.assertEqual(summary["total_files"], 10)
        self.assertEqual(summary["by_suffix"][".uuidd"], 4)
        self.assertEqual(summary["zero_byte_by_suffix"][".uuidd"], 2)


if __name__ == "__main__":
    unittest.main()
