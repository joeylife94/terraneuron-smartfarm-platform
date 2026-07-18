# Dependency Security Scanning

TerraNeuron runs the reusable `Security Scan` workflow for every pull request and `main`
push through the primary CI/CD pipeline. The same workflow also supports weekly and manual
runs.

## Two-pass policy

The workflow deliberately separates reporting from enforcement:

1. The reporting pass scans all vulnerability severities and uploads SARIF to GitHub code
   scanning. It does not fail the job because reporting must remain available for low,
   medium, unfixed, and informational findings.
2. The enforcement pass fails with exit code 1 when Trivy finds a **HIGH** or **CRITICAL**
   dependency vulnerability for which the current vulnerability database advertises a fix.

This policy makes a fixable high-impact dependency regression block PRs and `main`, while an
unfixed upstream vulnerability remains visible without permanently preventing development.
`ignore-unfixed` does not mean ignored operationally: unfixed findings remain in the SARIF
report and require monitoring until a fixed version becomes available.

## Exception policy

There is no blanket vulnerability allowlist. Any future suppression must be introduced in a
dedicated pull request and must identify the exact vulnerability, affected component,
technical rationale, owner, and expiration date. Severity-wide or package-wide exclusions are
not acceptable substitutes for remediation.

## Scope and limits

- The scan is a Trivy filesystem dependency scan of the checked-out repository.
- The gate covers fixable HIGH and CRITICAL dependency vulnerabilities.
- SARIF retains findings at every severity, including unfixed findings.
- Results depend on the vulnerability database available at scan time, so a previously green
  commit can fail on a later scheduled run when new advisory data is published.
- This does not replace deployed-image scanning, runtime protection, secret management, or a
  reachability assessment. Those require separate controls.

The policy contract is checked by `tests/test_security_scan_policy.py` before the Trivy scan
runs, preventing accidental removal of the blocking criteria or the full SARIF report.
