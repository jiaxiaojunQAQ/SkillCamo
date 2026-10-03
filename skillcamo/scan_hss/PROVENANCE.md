# PROVENANCE — scan_hss

- **Component**: HSS (hybrid security scanner) baseline — three-phase scanning
  (static rules, llm-guard semantic analysis, LLM classification over an
  8-dimension risk taxonomy).
- **Upstream**: academic baseline; see the paper's reference list (HSS).
- **License**: see README.md in this directory.
- **Role in paper**: baseline scanner "HSS".

## Local modifications (evaluation harness only)

- Hardened for batch evaluation (error isolation, deterministic settings).
- Directory-name leakage removal (evaluation hygiene).

Invoked via `skillcamo/unified_scanner/adapters/scan_hss.py`.
