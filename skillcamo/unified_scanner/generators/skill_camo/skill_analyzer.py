# Copyright 2026
#
# SKILL.md analyzer for image command injection.

"""
SKILL.md analyzer - extracts structure and context for LLM analysis.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List

import yaml

from .models import SkillContext, SkillSection

# Section name patterns (case-insensitive) that indicate natural insertion points
_SETUP_SECTION_PATTERNS = [
    "prerequisite", "prerequisites", "setup", "getting started", "installation",
    "configuration", "requirements", "before you begin", "quick start", "onboarding",
]

# YAML front matter fields that contain structured content
_STRUCTURED_CONTENT_FIELDS = ["goal", "subgoals", "skills", "interaction_policy"]

logger = logging.getLogger(__name__)


class SkillAnalyzer:
    """Analyzes SKILL.md structure and content"""

    def __init__(self, skill_path: Path):
        self.skill_path = Path(skill_path)
        self.skill_md = self.skill_path / "SKILL.md"

        if not self.skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found at {self.skill_md}")

    def analyze(self) -> SkillContext:
        """Analyze the skill and return context"""
        content = self.skill_md.read_text(encoding="utf-8")
        lines = content.split("\n")

        sections = self._extract_sections(content)
        has_resources = (self.skill_path / "resources").exists()

        return SkillContext(
            content=content,
            sections=sections,
            has_resources=has_resources,
            total_lines=len(lines),
        )

    def _extract_sections(self, content: str) -> List[SkillSection]:
        """Extract all sections from SKILL.md.

        Supports both:
        1. Traditional markdown headings (## Section Name)
        2. Structured content in YAML front matter (goal, subgoals, skills, interaction_policy)
        """
        sections = []

        # First, extract sections from YAML front matter if present
        yaml_sections = self._extract_yaml_sections(content)
        sections.extend(yaml_sections)

        # Then extract traditional markdown headings
        pattern = re.compile(r"^(#{1,6})\s+(.+)$")
        lines = content.split("\n")
        in_frontmatter = False
        frontmatter_end_line = 0

        for i, line in enumerate(lines):
            # Skip YAML front matter content
            if i == 0 and line.strip() == "---":
                in_frontmatter = True
                continue
            if in_frontmatter:
                if line.strip() == "---":
                    in_frontmatter = False
                    frontmatter_end_line = i
                continue

            match = pattern.match(line)
            if match:
                level = len(match.group(1))
                name = match.group(2).strip()
                sections.append(SkillSection(
                    name=name,
                    level=level,
                    start_line=i + 1,
                    content=line,
                ))

        return sections

    def _extract_yaml_sections(self, content: str) -> List[SkillSection]:
        """Extract sections from YAML front matter structured content fields."""
        sections = []
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return sections

        yaml_content = match.group(1)
        try:
            parsed = yaml.safe_load(yaml_content)
            if not isinstance(parsed, dict):
                return sections

            # Add sections for structured content fields
            for field in _STRUCTURED_CONTENT_FIELDS:
                if field in parsed:
                    value = parsed[field]
                    if isinstance(value, str):
                        sections.append(SkillSection(
                            name=field.title(),
                            level=2,
                            start_line=1,  # YAML front matter is at the beginning
                            content=f"## {field.title()}\n{value}",
                        ))
                    elif isinstance(value, list):
                        # Format list content
                        formatted_items = []
                        for item in value:
                            if isinstance(item, dict):
                                name = item.get("name", "")
                                desc = item.get("description", "")
                                if name and desc:
                                    formatted_items.append(f"- {name}: {desc}")
                                elif name:
                                    formatted_items.append(f"- {name}")
                                else:
                                    formatted_items.append(f"- {json.dumps(item)}")
                            else:
                                formatted_items.append(f"- {item}")
                        sections.append(SkillSection(
                            name=field.title(),
                            level=2,
                            start_line=1,
                            content=f"## {field.title()}\n" + "\n".join(formatted_items),
                        ))
                    elif isinstance(value, dict):
                        # Format dict content
                        formatted_lines = []
                        for k, v in value.items():
                            formatted_lines.append(f"- {k}: {v}")
                        sections.append(SkillSection(
                            name=field.title(),
                            level=2,
                            start_line=1,
                            content=f"## {field.title()}\n" + "\n".join(formatted_lines),
                        ))

        except yaml.YAMLError:
            pass

        return sections

    def get_full_content_for_llm(self) -> str:
        """Get the full content formatted for LLM consumption"""
        return self.analyze().content

    def suggest_insertion_point(self) -> str:
        """Analyze the SKILL.md structure and suggest where to insert new content.

        Returns a human-readable description of the recommended insertion location,
        suitable for inclusion in LLM prompts.

        Strategy:
        1. If content is in YAML front matter (new format), suggest adding to YAML or after front matter.
        2. If a setup/prerequisites section exists, suggest inserting there.
        3. If only high-level sections exist (overview, features, usage),
           suggest inserting after the overview and before usage instructions.
        4. Fallback: suggest creating a new "Setup" section after the intro.
        """
        context = self.analyze()
        sections = context.sections

        # Check if this is a new format skill with YAML front matter content
        if self._is_yaml_frontmatter_format():
            return self._suggest_yaml_insertion_point()

        if not sections:
            return (
                "No sections detected in the document. "
                "Add after the introductory paragraph and before any usage instructions."
            )

        # Strategy 1: find existing setup-like section
        for section in sections:
            name_lower = section.name.lower()
            if any(pat in name_lower for pat in _SETUP_SECTION_PATTERNS):
                return (
                    f'Insert into the existing "{section.name}" section '
                    f"(around line {section.start_line}). "
                    "Add the new content as a natural part of this section."
                )

        # Strategy 2: find overview/description and usage sections
        overview_idx = None
        usage_idx = None
        for i, section in enumerate(sections):
            name_lower = section.name.lower()
            if overview_idx is None and any(
                kw in name_lower for kw in ("overview", "about", "description", "introduction", "intro")
            ):
                overview_idx = i
            if usage_idx is None and any(
                kw in name_lower for kw in ("usage", "how to", "instructions", "example", "quick", "getting started")
            ):
                usage_idx = i

        if overview_idx is not None and usage_idx is not None:
            return (
                f'Insert between the "{sections[overview_idx].name}" and '
                f'"{sections[usage_idx].name}" sections. '
                "This places it after the overview but before usage instructions."
            )

        if overview_idx is not None:
            return (
                f'Insert after the "{sections[overview_idx].name}" section '
                f"(around line {sections[overview_idx].start_line}). "
                "Add a new subsection or paragraph naturally after the overview."
            )

        # Strategy 3: fallback — after first section
        first = sections[0]
        return (
            f'Insert after the "{first.name}" section '
            f"(around line {first.start_line}). "
            "Create a new setup-related subsection that fits naturally into the document flow."
        )

    def _is_yaml_frontmatter_format(self) -> bool:
        """Check if the SKILL.md uses the new YAML front matter format with structured content."""
        try:
            content = self.skill_md.read_text(encoding="utf-8", errors="ignore")
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not match:
                return False

            yaml_content = match.group(1)
            parsed = yaml.safe_load(yaml_content)
            if not isinstance(parsed, dict):
                return False

            # Check if any structured content fields exist
            return any(field in parsed for field in _STRUCTURED_CONTENT_FIELDS)

        except (yaml.YAMLError, OSError):
            return False

    def _suggest_yaml_insertion_point(self) -> str:
        """Suggest insertion point for skills using YAML front matter format."""
        try:
            content = self.skill_md.read_text(encoding="utf-8", errors="ignore")
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not match:
                return "Add content to the YAML front matter section."

            yaml_content = match.group(1)
            parsed = yaml.safe_load(yaml_content)
            if not isinstance(parsed, dict):
                return "Add content to the YAML front matter section."

            # Check which structured fields exist
            existing_fields = [f for f in _STRUCTURED_CONTENT_FIELDS if f in parsed]

            if "goal" in existing_fields:
                return (
                    "The skill uses YAML front matter format. "
                    "Consider adding a 'reference' or 'prerequisites' field to the YAML front matter, "
                    "or add content after the front matter section in the markdown body."
                )
            elif "subgoals" in existing_fields:
                return (
                    "The skill uses YAML front matter format with subgoals. "
                    "Add a new subgoal to the 'subgoals' list in the YAML front matter, "
                    "or add content after the front matter section in the markdown body."
                )
            elif "skills" in existing_fields:
                return (
                    "The skill uses YAML front matter format with skills list. "
                    "Add a new skill to the 'skills' list in the YAML front matter, "
                    "or add content after the front matter section in the markdown body."
                )
            else:
                return (
                    "The skill uses YAML front matter format. "
                    "Add content to the YAML front matter section or after it in the markdown body."
                )

        except (yaml.YAMLError, OSError):
            return "Add content to the YAML front matter section."


def load_script_command(script_path: Path) -> str:
    """Load the first command from a script file.

    Delegates to HarmfulScriptLoader.load_command (single implementation).
    """
    from .script_loader import HarmfulScriptLoader
    return HarmfulScriptLoader.load_command(script_path)
