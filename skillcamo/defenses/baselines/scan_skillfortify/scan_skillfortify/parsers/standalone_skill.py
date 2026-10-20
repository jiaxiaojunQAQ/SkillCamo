"""Parser for standalone SKILL.md files.

This is a minimal copy for integration into unified_scanner.
Reuses utilities from claude_skills.py.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from scan_skillfortify.parsers.base import ParsedSkill, SkillParser
from scan_skillfortify.parsers.claude_skills import (
    _FRONTMATTER_PATTERN,
    _extract_code_blocks,
    _extract_env_vars,
    _extract_shell_commands,
    _extract_urls,
)


class StandaloneSkillParser(SkillParser):
    """Parser for standalone SKILL.md files.

    Usage: To parse a skill, pass the directory containing ``SKILL.md``.
    The parser will look for ``SKILL.md`` in the specified directory.
    """

    def can_parse(self, path: Path) -> bool:
        """Check if the directory itself contains a SKILL.md file."""
        return path.is_dir() and (path / "SKILL.md").is_file()

    def parse(self, path: Path) -> list[ParsedSkill]:
        """Parse the SKILL.md file in the given directory."""
        skill_file = path / "SKILL.md"
        if not skill_file.is_file():
            return []

        skill = self._parse_file(skill_file, path.name)
        return [skill] if skill is not None else []

    def _parse_file(self, file_path: Path, fallback_name: str) -> ParsedSkill | None:
        """Parse a single SKILL.md file."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        # Extract frontmatter.
        name = fallback_name
        description = ""
        frontmatter_match = _FRONTMATTER_PATTERN.match(raw_content)
        if frontmatter_match:
            try:
                fm_data = yaml.safe_load(frontmatter_match.group(1))
                if isinstance(fm_data, dict):
                    name = fm_data.get("name", name)
                    description = fm_data.get("description", "")
            except yaml.YAMLError:
                pass

        # Extract security-relevant metadata from the full content.
        urls = _extract_urls(raw_content)
        env_vars = _extract_env_vars(raw_content)
        code_blocks = _extract_code_blocks(raw_content)
        shell_commands = _extract_shell_commands(raw_content)

        return ParsedSkill(
            name=name,
            version="unknown",
            source_path=file_path,
            format="standalone",
            description=description,
            instructions=raw_content,
            urls=urls,
            env_vars_referenced=env_vars,
            code_blocks=code_blocks,
            shell_commands=shell_commands,
            raw_content=raw_content,
        )
