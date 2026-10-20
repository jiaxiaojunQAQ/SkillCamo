"""Smoke tests: package imports and the paper's generator/scanner registries.

No API keys required.
"""

from __future__ import annotations


def test_core_imports():
    import skillcamo  # noqa: F401
    import skillcamo.framework  # noqa: F401
    import skillcamo.framework.entry  # noqa: F401
    import skillcamo.framework.pipeline.orchestrator  # noqa: F401
    import skillcamo.framework.pipeline.scanner_wrapper  # noqa: F401
    import skillcamo.defenses.execscan  # noqa: F401


def test_generator_registry_contains_exactly_paper_attacks():
    from skillcamo.attacks import GeneratorRegistry

    registered = set(GeneratorRegistry.list_all())
    assert registered == {
        "direct_scan",
        "skillject",
        "SkillCamo",
        "SkillCamo_cloze",
        "SkillCamo_split",
        "SkillCamo_replace",
    }


def test_scanner_set_is_paper_seven():
    from skillcamo.framework.capabilities import ALL_SCANNER_NAMES

    assert set(ALL_SCANNER_NAMES) == {
        "scan_cisco",
        "scan_hss",
        "scan_execscan",
        "scan_skillfortify",
        "scan_skill_vetter",
        "scan_skill_slowmist",
        "scan_skill_auditor",
    }


def test_adapter_registry_builds():
    from skillcamo.framework.adapters.registry import create_default_registry

    registry = create_default_registry()
    assert registry is not None
