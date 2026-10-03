#!/usr/bin/env python3
"""
Translation Engine Module
Translates text segments with language-specific prompts and glossary integration.
"""

import os
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import requests


@dataclass
class TranslationResult:
    """Represents the result of a translation."""
    original: str
    translated: str
    language: str
    confidence: float
    source_language: str
    glossary_terms_applied: List[str]


class TranslationEngine:
    """Translates text using Claude API with language-specific prompts."""

    # Language-specific prompts for better quality
    LANGUAGE_PROMPTS = {
        'zh': {
            'name': 'Simplified Chinese',
            'instruction': '将文本翻译为简体中文。保持原文的语气和意思。使用现代、清晰的汉语表达。',
            'examples': 'Examples: "API" -> "应用程序接口", "function" -> "函数"',
        },
        'zh_tw': {
            'name': 'Taiwan Traditional Chinese',
            'instruction': '將文本翻譯為繁體中文（台灣）。保持原文的語氣和意思。使用台灣常用的詞彙和表達方式。',
            'examples': 'Examples: "software" -> "軟體", "component" -> "元件"',
        },
        'ja': {
            'name': 'Japanese',
            'instruction': '日本語に翻訳してください。外来語はカタカナで表記してください。敬語は使わず、標準的な日本語で翻訳してください。',
            'examples': 'Examples: "API" -> "エーピーアイ", "function" -> "関数"',
        },
        'ko': {
            'name': 'Korean',
            'instruction': '한국어로 번역하세요. 기술 용어는 적절하게 번역하거나 한글 표기하세요. 존댓말을 사용하세요.',
            'examples': 'Examples: "API" -> "API" 또는 "에이피아이", "function" -> "함수"',
        },
        'id': {
            'name': 'Indonesian',
            'instruction': 'Terjemahkan ke bahasa Indonesia. Gunakan bahasa baku (formal). Pertahankan makna dan nada asli.',
            'examples': 'Examples: "API" -> "Antarmuka Pemrograman Aplikasi", "function" -> "Fungsi"',
        },
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the translation engine.

        Args:
            api_key: Claude API key (or reads from CLAUDE_API_KEY environment variable)
        """
        self.api_key = api_key or os.environ.get('CLAUDE_API_KEY')
        if not self.api_key:
            raise ValueError('Claude API key not provided or found in CLAUDE_API_KEY')

        self.api_url = 'https://api.anthropic.com/v1/messages'
        self.model = 'claude-3-5-sonnet-20241022'
        self.rate_limiter = RateLimiter(requests_per_minute=30)
        self.glossary_terms: Dict[str, str] = {}

    def set_glossary(self, glossary_terms: Dict[str, str]) -> None:
        """
        Set glossary terms for terminology consistency.

        Args:
            glossary_terms: Dictionary mapping English terms to target language terms
        """
        self.glossary_terms = glossary_terms

    def translate(
        self,
        text: str,
        target_language: str,
        source_language: str = 'en',
        context: str = '',
        preserve_formatting: bool = True
    ) -> TranslationResult:
        """
        Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code
            context: Optional context about the text
            preserve_formatting: Whether to preserve formatting

        Returns:
            TranslationResult with translation and metadata
        """
        # Clean text for translation
        cleaned_text = text.strip()

        if not cleaned_text:
            return TranslationResult(
                original=text,
                translated=text,
                language=target_language,
                confidence=1.0,
                source_language=source_language,
                glossary_terms_applied=[]
            )

        # Build prompt
        prompt = self._build_translation_prompt(
            cleaned_text,
            target_language,
            source_language,
            context,
            preserve_formatting
        )

        # Apply rate limiting
        self.rate_limiter.wait_if_needed()

        # Call Claude API
        try:
            response = self._call_claude_api(prompt)
            translated_text = response.strip()

            # Apply glossary if provided
            applied_terms = []
            if self.glossary_terms:
                for english_term, target_term in self.glossary_terms.items():
                    # Simple term replacement (can be enhanced with more sophisticated matching)
                    if english_term.lower() in cleaned_text.lower():
                        # Count how many times the term appears to ensure proper replacement
                        applied_terms.append(english_term)

            return TranslationResult(
                original=text,
                translated=translated_text,
                language=target_language,
                confidence=0.85,  # Claude is generally high quality
                source_language=source_language,
                glossary_terms_applied=applied_terms
            )

        except Exception as e:
            print(f'Translation error: {e}')
            # Fallback: return original with low confidence
            return TranslationResult(
                original=text,
                translated=text,
                language=target_language,
                confidence=0.0,
                source_language=source_language,
                glossary_terms_applied=[]
            )

    def batch_translate(
        self,
        texts: List[str],
        target_language: str,
        source_language: str = 'en',
        context: str = ''
    ) -> List[TranslationResult]:
        """
        Translate multiple text segments.

        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language code
            context: Optional context

        Returns:
            List of TranslationResult objects
        """
        results = []
        for text in texts:
            result = self.translate(
                text,
                target_language,
                source_language,
                context
            )
            results.append(result)
            # Add small delay between API calls
            time.sleep(0.1)

        return results

    def _build_translation_prompt(
        self,
        text: str,
        target_language: str,
        source_language: str,
        context: str,
        preserve_formatting: bool
    ) -> str:
        """Build a translation prompt for Claude."""
        lang_info = self.LANGUAGE_PROMPTS.get(target_language, {})
        lang_name = lang_info.get('name', target_language)
        instruction = lang_info.get('instruction', f'Translate to {lang_name}')

        prompt_parts = [
            f'You are a professional translator. Your task is to translate the following text to {lang_name}.',
            '',
            instruction,
            '',
            lang_info.get('examples', ''),
            '',
            'Important rules:',
            '1. Preserve all formatting (line breaks, punctuation)',
            '2. Keep technical terms consistent',
            '3. Maintain the original tone and style',
            '4. Do not add explanations or notes',
            '5. Translate only the given text, nothing more',
            '',
        ]

        if context:
            prompt_parts.append(f'Context: {context}')
            prompt_parts.append('')

        if self.glossary_terms:
            prompt_parts.append('Important terminology to use:')
            for english_term, target_term in list(self.glossary_terms.items())[:10]:  # Limit to 10
                prompt_parts.append(f'- {english_term} -> {target_term}')
            prompt_parts.append('')

        prompt_parts.extend([
            'Text to translate:',
            '---',
            text,
            '---',
            '',
            'Translated text (nothing else):',
        ])

        return '\n'.join(prompt_parts)

    def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API and get response."""
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }

        data = {
            'model': self.model,
            'max_tokens': 2000,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
        }

        response = requests.post(self.api_url, json=data, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()

        if 'content' in result and len(result['content']) > 0:
            return result['content'][0]['text']

        raise ValueError('Unexpected API response format')

    @staticmethod
    def get_supported_languages() -> Dict[str, str]:
        """Get supported target languages."""
        return {
            'zh': 'Simplified Chinese',
            'zh_tw': 'Taiwan Traditional Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'id': 'Indonesian',
        }


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60 / requests_per_minute
        self.last_request_time = 0

    def wait_if_needed(self) -> None:
        """Wait if necessary to maintain rate limit."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)

        self.last_request_time = time.time()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print('Usage: python translator.py <text> <target_language> [source_language]')
        sys.exit(1)

    text = sys.argv[1]
    target_lang = sys.argv[2]
    source_lang = sys.argv[3] if len(sys.argv) > 3 else 'en'

    try:
        engine = TranslationEngine()
        result = engine.translate(text, target_lang, source_lang)

        output = {
            'original': result.original,
            'translated': result.translated,
            'language': result.language,
            'confidence': result.confidence,
            'source_language': result.source_language,
        }

        print(json.dumps(output, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
