# Copyright 2026
#
# Cloze-style processing for image command injection.

"""
Cloze processor - handles fill-in-the-blank style command injection.

Approach:
1. Split command into tokens (whitespace + shell operators)
2. Filter common shell builtins / short flags / pure punctuation
3. Randomly sample N tokens (configured by ClozeConfig.max_blanks)
4. Replace each chosen token with ___1___, ___2___, ...
5. Cache results so repeat runs on the same script reproduce the same blanks
"""

from __future__ import annotations

import logging
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import ClozeConfig, ClozeResult

logger = logging.getLogger(__name__)


class ClozeNotApplicableError(Exception):
    """Raised when command has no maskable tokens at all."""
    pass


class ClozeProcessor:
    """Processes commands into cloze-style (fill-in-the-blank) format"""

    # 切分后过滤掉的 shell 通用关键字（保留这些会让挖空失去信息量）
    _COMMON_WORDS = {
        "curl", "wget", "bash", "sh", "python", "ruby", "perl",
        "grep", "awk", "sed", "cat", "echo", "ls", "cd", "pwd",
        "mkdir", "rm", "cp", "mv", "chmod", "chown", "sudo",
        "http", "https", "tcp", "udp", "if", "then", "fi", "do",
        "done", "while", "for", "in", "true", "false", "null",
    }

    def __init__(self, config: ClozeConfig):
        self.config = config
        self._blank_cache: Dict[str, ClozeResult] = {}

    def process(self, command: str, script_path: Path) -> ClozeResult:
        """Main entry point: process command into cloze format.

        Args:
            command: The command to process
            script_path: Path to the script file (for caching)

        Returns:
            ClozeResult with masked command and chosen tokens
        """
        cached = self._get_cached(script_path)
        if cached is not None:
            return cached

        target_n = self.config.max_blanks

        # Force-mask the egress-signalling spans FIRST (opt-in). These carry the
        # network signal (`-X POST`, `-d @-`, the URL) that the effect extractor
        # keys on; masking them denudes the text template so the whole egress must
        # be recovered from the image — the hard cloze case for a keyless scanner.
        forced = self._force_mask_spans(command) if self.config.force_mask_egress else []

        remaining_n = max(0, target_n - len(forced))
        tokens = self._extract_tokens(command)
        # Drop tokens already covered by a forced span (e.g. the URL, or `POST`
        # inside `-X POST`) so they are not double-masked with two indices.
        tokens = [t for t in tokens if not any(t in span for span in forced)]
        if len(tokens) > remaining_n:
            sampled = random.sample(tokens, remaining_n)
        else:
            sampled = list(tokens)
        keywords = forced + sampled

        if not keywords:
            raise ClozeNotApplicableError(
                f"No tokens available to mask in command: {command!r}."
            )

        if len(keywords) < target_n:
            logger.warning(
                "Cloze target=%d but only %d tokens available in command; "
                "output will have fewer blanks than requested.",
                target_n,
                len(keywords),
            )

        masked_command = self._mask_command(command, keywords)

        keyword_positions = []
        for kw in keywords:
            pos = command.find(kw)
            if pos >= 0:
                keyword_positions.append(pos)

        result = ClozeResult(
            original_command=command,
            masked_command=masked_command,
            keywords=keywords,
            keyword_positions=keyword_positions,
            image_keyword_map={i + 1: kw for i, kw in enumerate(keywords)},
        )

        self._cache_result(script_path, result)
        return result

    def _extract_tokens(self, command: str) -> List[str]:
        """从命令中切分出可挖空的 token 列表。

        按空格 + 常见 shell 操作符切分；过滤通用关键字、过短片段、纯标点；
        去重保持顺序；移除互为子串的 token（避免 mask 顺序冲突）。
        返回**按命令出现顺序**排列的 token——前 N 个就是挖空对象。
        """
        raw_tokens = re.split(r"[\s|;&<>()\[\]{}]+", command)

        seen: Set[str] = set()
        candidates: List[str] = []
        for token in raw_tokens:
            token = token.strip().strip("\"'`,")
            if not token:
                continue
            if token in seen:
                continue
            if token.lower() in self._COMMON_WORDS:
                continue
            if len(token) < 3:
                continue
            if not re.search(r"\w", token):
                continue
            seen.add(token)
            candidates.append(token)

        # 移除互为子串的 token（保留较长者）
        filtered: List[str] = []
        for token in candidates:
            if any(token != other and token in other for other in candidates):
                continue
            filtered.append(token)
        return filtered

    # Egress-signalling spans, in match priority. These are the substrings the
    # effect extractor keys on for a curl/wget exfil; a `-d @<path>` span also
    # sweeps the credential path into the image. Matched as whole units (not
    # word-split), so multi-word (`-X POST`) and short (`-d @-`) spans that the
    # normal token filter would drop are still maskable.
    _EGRESS_SPANS = [
        re.compile(r"-X\s*POST", re.IGNORECASE),
        re.compile(r"--data(?:-binary|-raw)?(?:\s*@\S+|\s*@-)?", re.IGNORECASE),
        re.compile(r"-d\s*@\S*"),
        re.compile(r"https?://\S+"),
    ]

    def _force_mask_spans(self, command: str) -> List[str]:
        """Return the egress-signalling spans of ``command`` in left-to-right
        order, non-overlapping. Used to force-mask the network signal into the
        image regardless of the length / common-word filters."""
        spans: List[tuple[int, int, str]] = []
        for pat in self._EGRESS_SPANS:
            for m in pat.finditer(command):
                spans.append((m.start(), m.end(), m.group(0)))
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        out: List[str] = []
        last_end = -1
        for start, end, text in spans:
            if start < last_end:  # overlaps an already-chosen span -> skip
                continue
            text = text.strip()
            if text:
                out.append(text)
                last_end = end
        return out

    def _mask_command(self, command: str, keywords: List[str]) -> str:
        """Replace keywords with ___1___, ___2___, etc.

        按长度降序替换，避免短 keyword 先吞掉长 keyword 的子串
        （如 'dump.txt' 会先匹配掉 '/tmp/dump.txt' 中的 'dump.txt' 部分），
        但每个 keyword 仍使用其原始下标作为占位符编号。

        Args:
            command: Original command
            keywords: List of keywords to replace

        Returns:
            Command with keywords replaced by numbered blanks
        """
        if not keywords:
            return command

        indexed = list(enumerate(keywords, start=1))
        indexed.sort(key=lambda pair: -len(pair[1]))

        masked = command
        for idx, keyword in indexed:
            placeholder = self.config.blank_format.format(index=idx)
            pattern = re.escape(keyword)
            masked = re.sub(pattern, placeholder, masked, count=1)

        return masked

    def _get_cached(self, script_path: Path) -> Optional[ClozeResult]:
        """Get cached cloze result for script"""
        return self._blank_cache.get(str(script_path))

    def _cache_result(self, script_path: Path, result: ClozeResult) -> None:
        """Cache cloze result for script"""
        self._blank_cache[str(script_path)] = result

    def clear_cache(self) -> None:
        """Clear the blank cache"""
        self._blank_cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached entries"""
        return len(self._blank_cache)


def create_cloze_processor(
    max_blanks: int = 5,
    blank_format: str = "___{index}___",
) -> ClozeProcessor:
    """Convenience function to create ClozeProcessor with defaults"""
    config = ClozeConfig(
        enabled=True,
        max_blanks=max_blanks,
        blank_format=blank_format,
    )
    return ClozeProcessor(config)
