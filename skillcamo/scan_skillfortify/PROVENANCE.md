# PROVENANCE — scan_skillfortify

- **Component**: SkillFortify static analyzer — capability inference,
  dangerous-pattern detection, capability-vs-declaration violation checking.
- **Upstream**: academic baseline; see the paper's reference list (SkillFortify).
- **License**: see README.md / pyproject.toml in this directory.
- **Role in paper**: baseline scanner "SkillFortify" (pure static, no API).

## Local modifications (evaluation harness only)

- Packaged as `scan_skillfortify` for the unified framework; timeout /
  error isolation for batch evaluation.

Invoked via `skillcamo/unified_scanner/adapters/scan_skillfortify.py`.
