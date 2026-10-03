# PROVENANCE — scan_cisco

- **Component**: Cisco AI Defense Skill Scanner
- **Upstream**: https://github.com/cisco-ai-defense/skill-scanner
- **License**: Apache-2.0 (see LICENSE in this directory)
- **Role in paper**: baseline scanner "Cisco" (static analysis + YARA + LLM + behavioral)
- **Vendored because**: the paper's evaluation requires the exact analyzed
  version plus small harness patches; upstream evolves independently.

## Local modifications (evaluation harness only, no detection-logic changes)

- Directory-name leakage removal: scanner must not see the adversarial
  skill's directory name when it encodes the attack (evaluation hygiene).
- Deterministic LLM settings (temperature handling unified across scanners).
- Timeouts / error isolation for batch evaluation.

Invoked via `skillcamo/unified_scanner/adapters/scan_cisco.py`.
