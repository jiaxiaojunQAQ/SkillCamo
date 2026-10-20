"""Parser registry for auto-detecting agent skill formats.

This is a minimal copy for integration into unified_scanner.
Only includes ClaudeSkillsParser and StandaloneSkillParser.
"""

from __future__ import annotations

from pathlib import Path

from scan_skillfortify.parsers.base import ParsedSkill, SkillParser
from scan_skillfortify.parsers.claude_skills import ClaudeSkillsParser
from scan_skillfortify.parsers.standalone_skill import StandaloneSkillParser


class ParserRegistry:
    """Registry of skill parsers for auto-discovery.

    Maintains an ordered list of ``SkillParser`` instances. The ``discover()``
    method tries each parser against a directory and aggregates results.
    """

    def __init__(self) -> None:
        self.parsers: list[SkillParser] = []

    def register(self, parser: SkillParser) -> None:
        """Add a parser to the registry."""
        self.parsers.append(parser)

    def discover(self, path: Path) -> list[ParsedSkill]:
        """Discover all skills in a directory using registered parsers."""
        all_skills: list[ParsedSkill] = []
        for parser in self.parsers:
            if parser.can_parse(path):
                skills = parser.parse(path)
                all_skills.extend(skills)
        return all_skills


def default_registry() -> ParserRegistry:
    """Create a ParserRegistry pre-loaded with built-in parsers.

    Includes:
    1. ClaudeSkillsParser -- Claude Code skills (.claude/skills/*.md)
    2. StandaloneSkillParser -- Standalone SKILL.md files (dir/SKILL.md)
    """
    registry = ParserRegistry()
    registry.register(ClaudeSkillsParser())
    registry.register(StandaloneSkillParser())
    return registry
