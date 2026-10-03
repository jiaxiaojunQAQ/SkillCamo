# Glossary Template & Guidelines

This document explains how to create and maintain glossaries for the markdown-multilingual-translator to ensure consistent terminology across all languages.

## Why Glossaries Matter

Glossaries ensure that the same English technical term always translates to the same word in each target language. This is critical for:

- **Consistency**: Users see familiar terms throughout documentation
- **Professionalism**: Proper terminology builds credibility
- **Searchability**: Consistent terms make documentation easier to search and index
- **Maintenance**: Updates apply uniformly across all languages
- **Compliance**: Some industries require specific terminology

## Glossary File Format

Glossaries are JSON files with the following structure:

```json
{
  "term": {
    "en": "English definition",
    "zh": "简体中文 (Simplified Chinese)",
    "zh_tw": "繁體中文 (Taiwan Traditional Chinese)",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
    "id": "Bahasa Indonesia (Indonesian)",
    "context": "Where/when to use this term",
    "alternatives": ["alt1", "alt2"],
    "technical_level": "beginner|intermediate|advanced",
    "category": "ui|api|general|database|security"
  }
}
```

## Field Descriptions

- **term** (key): The English base term used to identify this glossary entry
- **en**: English definition or clarification (1-2 sentences)
- **zh**: Translation for Simplified Chinese
- **zh_tw**: Translation for Taiwan Traditional Chinese
- **ja**: Translation for Japanese (in appropriate script)
- **ko**: Translation for Korean (in Hangul)
- **id**: Translation for Indonesian
- **context**: Brief description of when/where to use this term (1 sentence)
- **alternatives**: Optional array of alternative terms or abbreviations
- **technical_level**: Indicates complexity level (beginner = introductory, intermediate = some prior knowledge, advanced = specialized)
- **category**: Optional classification for organizing glossary terms

## Step-by-Step Guide to Creating a Glossary

### Step 1: Collect Your Terms

List all unique technical terms from your documentation:

```
1. API
2. Function
3. Parameter
4. Return value
5. Variable
6. Component
7. Hook
8. State
9. Props
10. Rendering
```

### Step 2: Research Translations

For each term, research the standard translation in each language:

- Consult official documentation in that language
- Check if technical standards exist (ISO, IEEE, etc.)
- Ask native speakers of each language for validation
- Refer to existing glossaries in your domain

### Step 3: Gather Context

For each term, note where and when it's used:

- Which documentation sections reference this term?
- What skill level is required to understand it?
- Are there common abbreviations or variants?

### Step 4: Build Your Glossary

Create a JSON file with all entries:

```json
{
  "API": {
    "en": "Application Programming Interface - a specification for how different software components communicate",
    "zh": "应用程序接口",
    "zh_tw": "應用程式介面",
    "ja": "アプリケーションプログラミングインターフェース",
    "ko": "응용 프로그램 인터페이스",
    "id": "Antarmuka Pemrograman Aplikasi",
    "context": "Used in any documentation describing how to interact with a service or library",
    "alternatives": ["Application Programming Interface", "Interface"],
    "technical_level": "beginner",
    "category": "api"
  },
  "Function": {
    "en": "A reusable block of code that performs a specific task and can be called multiple times",
    "zh": "函数",
    "zh_tw": "函式",
    "ja": "関数",
    "ko": "함수",
    "id": "Fungsi",
    "context": "Used in programming tutorials and API documentation",
    "alternatives": ["Method", "Subroutine", "Procedure"],
    "technical_level": "intermediate",
    "category": "general"
  }
}
```

### Step 5: Validate

Before using your glossary:

1. Have native speakers review each translation
2. Check syntax: JSON must be valid
3. Verify all six languages are present
4. Test with a small translation sample
5. Update based on translation results

## Common Technical Glossary Entries

This section provides a starting template with common terms used in software documentation:

### General Programming Terms

```json
{
  "Variable": {
    "en": "A named storage location that holds a value which can change during program execution",
    "zh": "变量",
    "zh_tw": "變數",
    "ja": "変数",
    "ko": "변수",
    "id": "Variabel",
    "context": "Used in programming tutorials and code examples",
    "technical_level": "beginner"
  },
  "Constant": {
    "en": "A named value that does not change during program execution",
    "zh": "常量",
    "zh_tw": "常數",
    "ja": "定数",
    "ko": "상수",
    "id": "Konstanta",
    "context": "Used when describing fixed values or configuration",
    "technical_level": "beginner"
  },
  "Loop": {
    "en": "A control structure that repeats a block of code until a condition is met",
    "zh": "循环",
    "zh_tw": "迴圈",
    "ja": "ループ",
    "ko": "루프",
    "id": "Perulangan",
    "context": "Used in algorithm and programming tutorials",
    "technical_level": "intermediate"
  },
  "Array": {
    "en": "An ordered collection of elements stored in a single variable",
    "zh": "数组",
    "zh_tw": "陣列",
    "ja": "配列",
    "ko": "배열",
    "id": "Array",
    "context": "Used in data structure and programming documentation",
    "technical_level": "intermediate"
  },
  "Object": {
    "en": "A collection of key-value pairs representing properties and methods",
    "zh": "对象",
    "zh_tw": "物件",
    "ja": "オブジェクト",
    "ko": "객체",
    "id": "Objek",
    "context": "Used in object-oriented programming documentation",
    "technical_level": "intermediate"
  }
}
```

### Web Development Terms

```json
{
  "DOM": {
    "en": "Document Object Model - a programming interface for HTML and XML documents",
    "zh": "文档对象模型",
    "zh_tw": "文件物件模型",
    "ja": "ドキュメントオブジェクトモデル",
    "ko": "문서 객체 모델",
    "id": "Model Objek Dokumen",
    "context": "Used in JavaScript and web development tutorials",
    "alternatives": ["Document Object Model"],
    "technical_level": "advanced"
  },
  "Component": {
    "en": "A reusable, self-contained UI element in a framework",
    "zh": "组件",
    "zh_tw": "元件",
    "ja": "コンポーネント",
    "ko": "컴포넌트",
    "id": "Komponen",
    "context": "Used in React, Vue, Angular documentation",
    "technical_level": "intermediate"
  },
  "Props": {
    "en": "Properties passed to a component to control its behavior or appearance",
    "zh": "属性",
    "zh_tw": "屬性",
    "ja": "プロップス",
    "ko": "props",
    "id": "Props",
    "context": "React-specific documentation; usually kept as 'props' in non-English versions",
    "technical_level": "intermediate"
  },
  "Hook": {
    "en": "A function that lets you 'hook into' React features without writing class components",
    "zh": "钩子",
    "zh_tw": "鉤子",
    "ja": "フック",
    "ko": "훅",
    "id": "Hook",
    "context": "React-specific feature; usually kept as 'hook' in non-English versions",
    "technical_level": "advanced"
  },
  "State": {
    "en": "Data that changes over time and affects component rendering",
    "zh": "状态",
    "zh_tw": "狀態",
    "ja": "状態",
    "ko": "상태",
    "id": "Status",
    "context": "Used in UI framework documentation",
    "technical_level": "intermediate"
  }
}
```

### Database & Backend Terms

```json
{
  "Database": {
    "en": "An organized collection of structured data stored and accessed electronically",
    "zh": "数据库",
    "zh_tw": "資料庫",
    "ja": "データベース",
    "ko": "데이터베이스",
    "id": "Basis Data",
    "context": "Used in backend and database documentation",
    "technical_level": "beginner"
  },
  "Query": {
    "en": "A request for data from a database",
    "zh": "查询",
    "zh_tw": "查詢",
    "ja": "クエリ",
    "ko": "쿼리",
    "id": "Kueri",
    "context": "Used in SQL and database documentation",
    "technical_level": "intermediate"
  },
  "Schema": {
    "en": "The structure or organization of a database or data model",
    "zh": "模式",
    "zh_tw": "結構描述",
    "ja": "スキーマ",
    "ko": "스키마",
    "id": "Skema",
    "context": "Used in database and API documentation",
    "technical_level": "advanced"
  },
  "Index": {
    "en": "A data structure that improves the speed of data retrieval operations",
    "zh": "索引",
    "zh_tw": "索引",
    "ja": "インデックス",
    "ko": "인덱스",
    "id": "Indeks",
    "context": "Used in database optimization documentation",
    "technical_level": "advanced"
  }
}
```

## Domain-Specific Glossaries

### For API Documentation

```json
{
  "Endpoint": {
    "en": "A specific URL where an API can be accessed",
    "zh": "端点",
    "zh_tw": "端點",
    "ja": "エンドポイント",
    "ko": "엔드포인트",
    "id": "Titik Akhir",
    "context": "API documentation",
    "technical_level": "intermediate"
  },
  "Request": {
    "en": "A message sent to an API asking for data or action",
    "zh": "请求",
    "zh_tw": "請求",
    "ja": "リクエスト",
    "ko": "요청",
    "id": "Permintaan",
    "context": "API documentation",
    "technical_level": "intermediate"
  },
  "Response": {
    "en": "Data or status information returned by an API after processing a request",
    "zh": "响应",
    "zh_tw": "回應",
    "ja": "レスポンス",
    "ko": "응답",
    "id": "Respons",
    "context": "API documentation",
    "technical_level": "intermediate"
  },
  "Authentication": {
    "en": "The process of verifying the identity of a user or application",
    "zh": "身份验证",
    "zh_tw": "身份驗證",
    "ja": "認証",
    "ko": "인증",
    "id": "Autentikasi",
    "context": "Security and API documentation",
    "technical_level": "intermediate"
  }
}
```

### For DevOps Documentation

```json
{
  "Container": {
    "en": "A lightweight, standalone executable package containing code and all dependencies",
    "zh": "容器",
    "zh_tw": "容器",
    "ja": "コンテナ",
    "ko": "컨테이너",
    "id": "Kontainer",
    "context": "Docker and DevOps documentation",
    "technical_level": "advanced"
  },
  "Deploy": {
    "en": "To release or put into production an application or update",
    "zh": "部署",
    "zh_tw": "部署",
    "ja": "デプロイ",
    "ko": "배포",
    "id": "Terapkan",
    "context": "DevOps and release documentation",
    "technical_level": "intermediate"
  }
}
```

## Using Your Glossary

Once created, use your glossary with the translator:

```bash
python scripts/translate_markdown.py \
  --input document.md \
  --output document_zh.md \
  --target-language zh \
  --glossary custom_glossary.json
```

## Maintaining Your Glossary

### Regular Updates

1. **After each translation**: Review translations and add any new terms
2. **Quarterly review**: Check for outdated terminology
3. **Version control**: Track changes to glossary versions
4. **Feedback incorporation**: Integrate corrections from native speakers

### Glossary Versioning

Include version information in your glossary file:

```json
{
  "_metadata": {
    "version": "1.0.0",
    "last_updated": "2024-03-18",
    "updated_by": "translator_name",
    "languages": ["en", "zh", "zh_tw", "ja", "ko", "id"],
    "notes": "Initial glossary for React documentation"
  },
  "API": {
    "en": "Application Programming Interface...",
    ...
  }
}
```

## Validation Checklist for Glossaries

- [ ] All entries have translations for all six languages
- [ ] JSON syntax is valid (test with `jq . glossary.json`)
- [ ] Translations are reviewed by native speakers
- [ ] Context is clear for each term
- [ ] No duplicate or conflicting entries
- [ ] Technical level is appropriate
- [ ] Abbreviations are noted in alternatives
- [ ] No English articles or extra words in translations

## Glossary Sharing & Collaboration

### Export for Review

Convert your glossary to a table for easier review:

```bash
python -c "
import json
with open('glossary.json') as f:
    data = json.load(f)
print('Term | English | Chinese | Japanese | Korean | Indonesian')
print('-----|---------|---------|----------|--------|----------')
for term, entry in data.items():
    if term.startswith('_'): continue
    print(f'{term} | {entry[\"en\"][:20]}... | {entry[\"zh\"]} | {entry[\"ja\"]} | {entry[\"ko\"]} | {entry[\"id\"]}')
"
```

### Merge Multiple Glossaries

Combine glossaries from different domains:

```python
import json

# Load multiple glossaries
glossaries = []
for filename in ['api_glossary.json', 'web_glossary.json', 'general_glossary.json']:
    with open(filename) as f:
        glossaries.append(json.load(f))

# Merge (later glossaries override earlier ones for duplicate keys)
merged = {}
for glossary in glossaries:
    merged.update(glossary)

# Save
with open('combined_glossary.json', 'w', encoding='utf-8') as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
```

## Troubleshooting Glossary Issues

### Issue: Translations not being applied

1. Check JSON syntax is valid
2. Verify term keys match exactly (case-sensitive)
3. Ensure target language code is correct
4. Check file encoding is UTF-8

### Issue: English term appears in output

1. Term may not be in glossary - add it
2. Term might be in code or link - should not be translated
3. Glossary may be using different term form

### Issue: Inconsistent translations

1. Check for duplicate entries with different translations
2. Review glossary for typos in translation values
3. Merge conflicting glossaries carefully
4. Test with specific term to identify source

