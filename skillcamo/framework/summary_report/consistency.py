# Copyright 2026
#
# Cross-scanner consistency analysis.

"""
Analyzes cross-scanner agreement and divergence.

Metrics:
- Agreement rate: fraction of skills where two scanners agree (both detected or both clean)
- Jaccard similarity: overlap of detection sets, ignoring clean-clean agreement
- Sensitivity ranking: per-scanner detection rate across all processed skills
"""

from __future__ import annotations

import logging
from itertools import combinations

from .models import ConsistencyAnalysis, PerSkillScannerVerdict, ScannerPairAgreement

logger = logging.getLogger(__name__)

# Verdicts considered "active" (scanner ran and produced a result)
_ACTIVE_VERDICTS = {"detected", "clean"}


class ConsistencyAnalyzer:
    """Analyzes cross-scanner agreement and divergence."""

    @staticmethod
    def analyze(
        per_skill_verdicts: list[PerSkillScannerVerdict],
    ) -> ConsistencyAnalysis | None:
        """Run full pairwise consistency analysis.

        Returns None if fewer than 2 scanners have active verdicts.
        """
        # Collect all scanner names that have at least one active verdict
        active_scanners = ConsistencyAnalyzer._get_active_scanners(per_skill_verdicts)
        if len(active_scanners) < 2:
            logger.debug("Skipping consistency analysis: fewer than 2 active scanners (%s)", active_scanners)
            return None

        # Pairwise analysis
        pairwise = ConsistencyAnalyzer._compute_pairwise(active_scanners, per_skill_verdicts)

        # Sensitivity ranking
        sensitivity = ConsistencyAnalyzer._compute_sensitivity(active_scanners, per_skill_verdicts)

        # Overall agreement
        if pairwise:
            overall_agreement = sum(p.agreement_rate for p in pairwise) / len(pairwise)
            worst = min(pairwise, key=lambda p: p.agreement_rate)
            most_disagreeable = (worst.scanner_a, worst.scanner_b)
        else:
            overall_agreement = 0.0
            most_disagreeable = None

        return ConsistencyAnalysis(
            pairwise_agreements=pairwise,
            per_skill_verdicts=per_skill_verdicts,
            overall_agreement_rate=overall_agreement,
            most_disagreeable_pair=most_disagreeable,
            scanner_sensitivity_ranking=sensitivity,
        )

    @staticmethod
    def build_verdicts_from_batch_skill_results(
        skill_results: list,
    ) -> list[PerSkillScannerVerdict]:
        """Extract per-skill, per-scanner verdicts from BatchSkillResult list.

        Each BatchSkillResult has a scanner_summary property returning
        dict[scanner_name, {detected, clean, error, severity_counts}].
        """
        verdicts = []
        for result in skill_results:
            name = result.spec.name if hasattr(result.spec, "name") else "unknown"
            scanner_verdicts: dict[str, str] = {}

            for scanner_name, stats in result.scanner_summary.items():
                detected = stats.get("detected", 0)
                clean = stats.get("clean", 0)
                error = stats.get("error", 0)

                if detected > 0:
                    scanner_verdicts[scanner_name] = "detected"
                elif clean > 0 and detected == 0:
                    scanner_verdicts[scanner_name] = "clean"
                elif error > 0 and detected == 0 and clean == 0:
                    scanner_verdicts[scanner_name] = "error"
                else:
                    scanner_verdicts[scanner_name] = "skipped"

            verdicts.append(PerSkillScannerVerdict(
                skill_name=name,
                scanner_verdicts=scanner_verdicts,
            ))
        return verdicts

    @staticmethod
    def build_verdicts_from_scan_results(
        results: list[dict],
    ) -> list[PerSkillScannerVerdict]:
        """Extract per-skill, per-scanner verdicts from list of scan result dicts.

        Each dict has summary.scanner_summaries[{scanner_name, is_safe, status}].
        """
        verdicts = []
        for result in results:
            skill_path = result.get("skill_path", "unknown")
            name = skill_path.rsplit("/", 1)[-1] if "/" in skill_path else skill_path
            scanner_verdicts: dict[str, str] = {}

            summary = result.get("summary", {})
            for scanner_summary in summary.get("scanner_summaries", []):
                scanner_name = scanner_summary.get("scanner_name", "")
                status = scanner_summary.get("status", "unknown")
                is_safe = scanner_summary.get("is_safe")

                if status == "failed":
                    scanner_verdicts[scanner_name] = "error"
                elif status == "skipped":
                    scanner_verdicts[scanner_name] = "skipped"
                elif is_safe is True:
                    scanner_verdicts[scanner_name] = "clean"
                elif is_safe is False:
                    scanner_verdicts[scanner_name] = "detected"
                else:
                    scanner_verdicts[scanner_name] = "skipped"

            verdicts.append(PerSkillScannerVerdict(
                skill_name=name,
                scanner_verdicts=scanner_verdicts,
            ))
        return verdicts

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _get_active_scanners(verdicts: list[PerSkillScannerVerdict]) -> list[str]:
        """Collect scanner names with at least one active (non-skipped) verdict."""
        scanners: set[str] = set()
        for v in verdicts:
            for scanner_name, verdict in v.scanner_verdicts.items():
                if verdict in _ACTIVE_VERDICTS:
                    scanners.add(scanner_name)
        return sorted(scanners)

    @staticmethod
    def _compute_pairwise(
        active_scanners: list[str],
        verdicts: list[PerSkillScannerVerdict],
    ) -> list[ScannerPairAgreement]:
        """Compute pairwise agreement for all scanner combinations."""
        results: list[ScannerPairAgreement] = []

        for scanner_a, scanner_b in combinations(active_scanners, 2):
            both_detected = 0
            both_clean = 0
            detected_by_a: set[str] = set()
            detected_by_b: set[str] = set()
            total_compared = 0

            for v in verdicts:
                va = v.scanner_verdicts.get(scanner_a)
                vb = v.scanner_verdicts.get(scanner_b)

                # Skip if either scanner didn't process this skill
                if va not in _ACTIVE_VERDICTS or vb not in _ACTIVE_VERDICTS:
                    continue

                total_compared += 1
                skill = v.skill_name

                if va == "detected":
                    detected_by_a.add(skill)
                if vb == "detected":
                    detected_by_b.add(skill)

                if va == "detected" and vb == "detected":
                    both_detected += 1
                elif va == "clean" and vb == "clean":
                    both_clean += 1

            if total_compared == 0:
                agreement = 0.0
                co_det = 0.0
                co_clean = 0.0
                jaccard = 0.0
            else:
                agreement = (both_detected + both_clean) / total_compared
                co_det = both_detected / total_compared
                co_clean = both_clean / total_compared

                union = detected_by_a | detected_by_b
                intersection = detected_by_a & detected_by_b
                jaccard = len(intersection) / len(union) if union else 0.0

            results.append(ScannerPairAgreement(
                scanner_a=scanner_a,
                scanner_b=scanner_b,
                agreement_rate=agreement,
                co_detection_rate=co_det,
                co_clean_rate=co_clean,
                jaccard_similarity=jaccard,
                total_comparisons=total_compared,
            ))

        return results

    @staticmethod
    def _compute_sensitivity(
        active_scanners: list[str],
        verdicts: list[PerSkillScannerVerdict],
    ) -> list[tuple[str, float]]:
        """Compute per-scanner detection rate, sorted descending."""
        rankings: list[tuple[str, float]] = []

        for scanner in active_scanners:
            detected = 0
            total_active = 0

            for v in verdicts:
                verdict = v.scanner_verdicts.get(scanner)
                if verdict in _ACTIVE_VERDICTS:
                    total_active += 1
                    if verdict == "detected":
                        detected += 1

            rate = detected / total_active if total_active > 0 else 0.0
            rankings.append((scanner, rate))

        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
