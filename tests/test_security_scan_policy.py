"""Contract tests for the repository's blocking Trivy policy."""

from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "security-scan.yml"
)


def step_block(workflow: str, step_name: str) -> str:
    marker = f"- name: {step_name}"
    start = workflow.index(marker)
    next_step = workflow.find("\n      - name:", start + len(marker))
    return workflow[start:] if next_step == -1 else workflow[start:next_step]


class SecurityScanPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_complete_report_is_non_blocking_and_uploaded_even_after_failure(self) -> None:
        report = step_block(
            self.workflow,
            "🔍 Generate Complete Trivy SARIF Report",
        )
        upload = step_block(
            self.workflow,
            "📊 Upload Trivy Results to GitHub Security",
        )

        self.assertIn("uses: aquasecurity/trivy-action@v0.36.0", report)
        self.assertIn("format: 'sarif'", report)
        self.assertIn("exit-code: '0'", report)
        self.assertIn("ignore-unfixed: false", report)
        self.assertIn("UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL", report)
        self.assertIn("if: ${{ always()", upload)
        self.assertIn("trivy-results.sarif", upload)

    def test_gate_blocks_only_fixable_high_and_critical_vulnerabilities(self) -> None:
        gate = step_block(
            self.workflow,
            "🚫 Enforce Fixable High and Critical Vulnerability Gate",
        )

        self.assertIn("if: always()", gate)
        self.assertIn("--scanners vuln", gate)
        self.assertIn("--ignore-unfixed", gate)
        self.assertIn("--severity HIGH,CRITICAL", gate)
        self.assertIn("--exit-code 1", gate)
        self.assertIn("--format table", gate)


if __name__ == "__main__":
    unittest.main()
