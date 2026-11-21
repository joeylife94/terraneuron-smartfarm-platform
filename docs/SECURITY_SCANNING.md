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

## Monitored unfixed findings

These findings appear in SARIF only. They are not suppressed and they do not block the gate,
because no fixed version exists. Each one is reassessed when a fix is published or when the
affected component's deployment changes.

### chromadb 0.4.22 (terra-cortex)

Assessed 2026-11-08. Both advisories affect chromadb 0.4.17 through 1.5.9, which was the latest
release at the time of assessment, so upgrading chromadb does not remediate either one.

| Advisory | Severity | Precondition | terra-cortex exposure |
| --- | --- | --- | --- |
| CVE-2026-45833 / GHSA-36p7-vc44-83pf | CRITICAL 9.4 | Authenticated client with `UPDATE_COLLECTION` calls the Chroma server collection API (`/api/v2/tenants/.../collections/{id}`) with an attacker-chosen model repository and `trust_remote_code` | Not reachable |
| CVE-2026-45830 / GHSA-2wm9-hf6c-p5cr | HIGH 8.8 | Authenticated Chroma server client uses a collection UUID to cross tenant boundaries | Not reachable |

Rationale:

- terra-cortex uses chromadb only as an embedded, in-process store. The
  `langchain_community` `Chroma(persist_directory=...)` wrapper creates a local persistent
  client (`chromadb.Client(Settings(is_persistent=True))`) in `src/rag_advisor.py`,
  `src/ingest_knowledge.py` and `src/knowledge_collector.py`.
- No Chroma HTTP server runs anywhere. No compose service exists for it and no code uses
  `HttpClient` or `chroma run`. Only terra-cortex's own code calls chromadb, and its single
  default tenant gives no tenant boundary to cross.
- The wrapper passes `embedding_function=None` to chromadb. Embeddings are computed by
  `HuggingFaceEmbeddings` with the hardcoded `all-MiniLM-L6-v2` model, with no
  `trust_remote_code` and no request-controlled model name.

Reassess before deploying Chroma as a network service, before exposing collection management
over HTTP, or when the advisories publish a fixed version.

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
