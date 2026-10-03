#!/usr/bin/env python3
"""
Language Detection Module
Detects the source language of Markdown content.
"""

import re
from typing import Dict, Tuple, Optional


class LanguageDetector:
    """Detects the source language of text content."""

    # Character ranges for language detection
    LANGUAGE_PATTERNS = {
        'zh': {
            'chars': r'[\u4e00-\u9fff]',  # CJK Unified Ideographs
            'name': 'Simplified Chinese',
        },
        'zh_tw': {
            'chars': r'[\u4e00-\u9fff]',  # CJK Unified Ideographs (same as Simplified)
            'name': 'Taiwan Traditional Chinese',
        },
        'ja': {
            'hiragana': r'[\u3040-\u309f]',
            'katakana': r'[\u30a0-\u30ff]',
            'kanji': r'[\u4e00-\u9fff]',
            'name': 'Japanese',
        },
        'ko': {
            'chars': r'[\uac00-\ud7af]',  # Hangul Syllables
            'name': 'Korean',
        },
        'id': {
            'name': 'Indonesian',
            'keywords': [
                'adalah', 'yang', 'dan', 'untuk', 'di', 'dapat', 'ini', 'atau',
                'dari', 'dengan', 'telah', 'karena', 'lebih', 'akan', 'tersebut'
            ],
        },
        'en': {
            'name': 'English',
            'keywords': [
                'the', 'is', 'and', 'to', 'of', 'a', 'in', 'that', 'it', 'for',
                'this', 'you', 'are', 'with', 'from', 'be', 'or', 'have', 'by',
                'as', 'on', 'at', 'can', 'we', 'will', 'your', 'not', 'all', 'if'
            ],
        },
    }

    def __init__(self):
        self.detected_language = None
        self.confidence = 0.0

    def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect the language of the given text.

        Args:
            text: The text to analyze

        Returns:
            Tuple of (language_code, confidence_score)
            confidence_score is between 0.0 and 1.0
        """
        # Clean text: remove code blocks and HTML
        cleaned_text = self._clean_text(text)

        # Calculate scores for each language
        scores = {}

        # Check for CJK characters
        cjk_count = len(re.findall(r'[\u4e00-\u9fff]', cleaned_text))

        if cjk_count > 0:
            # Distinguish between Chinese and Japanese
            ja_count = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', cleaned_text))

            if ja_count > cjk_count * 0.1:  # 10% or more hiragana/katakana
                scores['ja'] = 0.9
            else:
                # Try to distinguish between Simplified and Traditional Chinese
                # Simplified has more specific characters
                simplified_markers = re.findall(
                    r'[\u7b80\u4e2b\u6574\u4f53\u65e0\u9700\u6765\u5904\u4e8b\u53ef\u80fd\u6700\u540e]',
                    cleaned_text
                )
                if len(simplified_markers) > 0:
                    scores['zh'] = 0.85
                else:
                    scores['zh_tw'] = 0.80
                    scores['zh'] = 0.75

        # Check for Korean Hangul
        hangul_count = len(re.findall(r'[\uac00-\ud7af]', cleaned_text))
        if hangul_count > 0:
            scores['ko'] = 0.9

        # Check for English
        if len(cleaned_text) > 0:
            word_score = self._score_english_words(cleaned_text)
            if word_score > 0.05:
                scores['en'] = word_score

        # Check for Indonesian
        if len(cleaned_text) > 0:
            id_score = self._score_indonesian_words(cleaned_text)
            if id_score > 0.05:
                scores['id'] = id_score

        # Determine the language with highest score
        if not scores:
            # Default to English if no clear indicators
            self.detected_language = 'en'
            self.confidence = 0.3
        else:
            self.detected_language = max(scores, key=scores.get)
            self.confidence = scores[self.detected_language]

        return self.detected_language, self.confidence

    def _clean_text(self, text: str) -> str:
        """Remove code blocks and other non-translatable content."""
        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)

        # Remove inline code
        text = re.sub(r'`[^`]+`', '', text)

        # Remove URLs
        text = re.sub(r'https?://[^\s]+', '', text)

        # Remove HTML
        text = re.sub(r'<[^>]+>', '', text)

        # Remove Markdown symbols
        text = re.sub(r'[#*_\[\](){}~]', '', text)

        return text.lower()

    def _score_english_words(self, text: str) -> float:
        """Score text based on English keyword frequency."""
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return 0.0

        en_keywords = set(self.LANGUAGE_PATTERNS['en']['keywords'])
        keyword_count = sum(1 for word in words if word in en_keywords)

        return keyword_count / len(words)

    def _score_indonesian_words(self, text: str) -> float:
        """Score text based on Indonesian keyword frequency."""
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return 0.0

        id_keywords = set(self.LANGUAGE_PATTERNS['id']['keywords'])
        keyword_count = sum(1 for word in words if word in id_keywords)

        return keyword_count / len(words)

    def get_language_name(self, code: str) -> str:
        """Get the display name for a language code."""
        if code in self.LANGUAGE_PATTERNS:
            return self.LANGUAGE_PATTERNS[code]['name']
        return code

    @staticmethod
    def get_supported_languages() -> Dict[str, str]:
        """Get all supported language codes and names."""
        return {
            'en': 'English',
            'zh': 'Simplified Chinese',
            'zh_tw': 'Taiwan Traditional Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'id': 'Indonesian',
        }


def detect_language(text: str) -> Tuple[str, float]:
    """Convenience function to detect language."""
    detector = LanguageDetector()
    return detector.detect(text)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage: python language_detector.py <file>')
        sys.exit(1)

    file_path = sys.argv[1]

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    detector = LanguageDetector()
    language, confidence = detector.detect(content)

    print(f'Detected Language: {detector.get_language_name(language)} ({language})')
    print(f'Confidence: {confidence:.2%}')
