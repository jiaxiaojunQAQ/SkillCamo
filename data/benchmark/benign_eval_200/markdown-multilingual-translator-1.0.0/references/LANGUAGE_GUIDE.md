# Language-Specific Translation Guide

This guide provides language-specific conventions, cultural considerations, and best practices for translating documentation into each of the six supported languages.

## English

### Language Characteristics

English is the base language for most technical documentation. When translating **into** English from other languages, consider these conventions:

- **Grammar**: Subject-Verb-Object (SVO) syntax
- **Capitalization**: Sentence case for paragraphs, Title Case for headings
- **Punctuation**: Periods end sentences; commas separate clauses
- **Spacing**: Single space after periods; spaces around operators and punctuation
- **Contractions**: Use contractions (don't, can't, it's) in casual documentation; avoid in formal technical writing
- **Terminology**: Use consistent, precise technical terms; avoid jargon without explanation

### Writing Conventions

- Headings should be in Title Case (capitalize primary words)
- Code terminology should match official documentation (e.g., "JavaScript", "React", not "java script")
- Use active voice: "You can access" instead of "Access can be obtained"
- Keep sentences concise: avoid nested clauses when possible

### Example English Text

```
# Getting Started with React

React is a JavaScript library for building user interfaces with reusable components.

## Installation

To install React, use npm or yarn:

```bash
npm install react react-dom
```

## Creating Your First Component

A React component is a JavaScript function that returns JSX:

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```
```

## Simplified Chinese (中文 - 简体)

### Language Characteristics

- **Grammar**: Subject-Verb-Object (SVO); flexible word order
- **Script**: Simplified characters (≈8,000 characters for general use)
- **Punctuation**: Chinese punctuation marks (。 ， ： ；)
- **Spacing**: No spaces between words; spaces only around code and English terms
- **Tone**: Formal and technical documentation prefers classical patterns
- **Numbers**: Use Arabic numerals; avoid large character numerals in technical content

### Writing Conventions

- **Headings**: Use "##" syntax; text follows standard Chinese capitalization
- **Code terminology**: Keep English terms for programming concepts (React, JavaScript, API)
- **Emphasis**: Use brackets for technical terms: 【React】, 【JavaScript】
- **Lists**: Use "- " for bullet points; maintain consistent indentation
- **Punctuation spacing**: No space before punctuation; space after period/comma
- **Consistency**: Maintain glossary of English terms and their Chinese equivalents

### Character Mapping

| English Term | Simplified Chinese | Notes |
|--------------|-------------------|-------|
| API | 应用程序接口 | Alternative: API (English commonly used in tech) |
| Function | 函数 | In context of programming |
| Parameter | 参数 | Method parameters or function arguments |
| Return | 返回 | Returning from a function |
| Variable | 变量 | Programming variable |
| Library | 库 | Code library or package |
| Component | 组件 | UI component in frameworks |

### Example Chinese Text

```
# React 入门指南

React 是一个用于构建用户界面的 JavaScript 库，采用可重用的组件。

## 安装

使用 npm 或 yarn 安装 React：

```bash
npm install react react-dom
```

## 创建第一个组件

React 组件是返回 JSX 的 JavaScript 函数：

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```
```

### Common Pitfalls

- Do not add spaces around Chinese text (except before/after code)
- Avoid mixing Simplified and Traditional characters
- Keep English technical terms in English for consistency
- Use proper Chinese quotation marks: 「」or 『』 instead of " "

---

## Taiwan Traditional Chinese (繁體中文)

### Language Characteristics

- **Grammar**: Subject-Verb-Object (SVO); similar to Simplified but with classical patterns
- **Script**: Traditional characters (≈13,000 characters; ≈7,000 for general use)
- **Punctuation**: Traditional Chinese marks (。 ， ： ；); comma spacing follows Taiwan standards
- **Spacing**: No spaces between words; spaces only around code and English terms
- **Tone**: More formal and classical than Simplified Chinese; stronger separation between English terms
- **Regional terms**: Uses Taiwan-specific vocabulary (e.g., "軟體" for software, not "软件")

### Writing Conventions

- **Headings**: Use "##" syntax with Traditional characters
- **Code terminology**: Keep English terms; apply【】brackets for clarity
- **Emphasis**: Use Traditional Chinese emphasis marks
- **Lists**: Use "- " with proper indentation
- **Spacing**: Space after traditional punctuation (following Taiwan conventions)
- **Terminology**: Use Taiwan-standard vocabulary; avoid mainland Simplified translations

### Character Mapping (Comparing Simplified vs. Traditional)

| English Term | Simplified | Traditional | Taiwan Preferred |
|--------------|-----------|-----------|-----------------|
| Software | 软件 | 軟件 | 軟體 |
| Program | 程序 | 程序 | 程式 |
| System | 系统 | 系統 | 系統 |
| Function | 函数 | 函數 | 函式 |
| Variable | 变量 | 變量 | 變數 |
| Parameter | 参数 | 參數 | 參數 |

### Example Taiwan Traditional Text

```
# React 入門指南

React 是一個用於構建使用者介面的 JavaScript 程式庫，採用可重複使用的元件。

## 安裝

使用 npm 或 yarn 安裝 React：

```bash
npm install react react-dom
```

## 建立第一個元件

React 元件是傳回 JSX 的 JavaScript 函式：

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```
```

### Common Pitfalls

- Do not confuse Traditional with Simplified characters
- Use Taiwan-specific vocabulary (e.g., 軟體, not 软件)
- Maintain consistent spacing after traditional punctuation
- Keep English technical terms clearly marked with【】

---

## Japanese (日本語)

### Language Characteristics

- **Grammar**: Subject-Object-Verb (SOV); particles mark grammatical relationships
- **Script**: Mixture of Hiragana (ひらがな), Katakana (カタカナ), and Kanji (漢字)
- **Punctuation**: Japanese periods (。) and commas (、); no space before punctuation
- **Spacing**: No spaces between words; spaces around English terms and code
- **Formality**: Three levels of politeness (casual, polite, honorific); use polite form (敬語) for technical writing
- **Reading aids**: Furigana (small characters above Kanji) for pronunciation; typically omitted in technical docs

### Writing Conventions

- **Headings**: Use "##" syntax; can use both Kanji and Hiragana
- **Katakana for foreign words**: Use Katakana for English-origin technical terms (プログラミング = programming)
- **Particles**: Proper use of を、に、で、から particles
- **Polite form**: Use ます/ます form and です for formal writing
- **Code terminology**: Use Katakana for English terms (API = エーピーアイ or keep as API)
- **Lists**: Use "- " with Hiragana bullets (・) in traditional Japanese lists

### Character Mapping (English to Japanese)

| English | Japanese | Katakana | Notes |
|---------|----------|----------|-------|
| API | エーピーアイ | Often kept as "API" in tech | Application Programming Interface |
| Function | 関数 (かんすう) | - | Mathematical/programming function |
| Parameter | パラメータ | - | Function parameter |
| Return | 戻る (もどる) | - | Return from function |
| Variable | 変数 (へんすう) | - | Programming variable |
| Library | ライブラリ | - | Code library |
| Component | コンポーネント | - | UI component |

### Example Japanese Text

```
# React 入門ガイド

React は、再利用可能なコンポーネントを使用してユーザー インターフェースを構築するための JavaScript ライブラリです。

## インストール

npm または yarn を使用して React をインストールします。

```bash
npm install react react-dom
```

## 最初のコンポーネント作成

React コンポーネントは、JSX を返す JavaScript 関数です。

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```
```

### Polite Form Examples

| Casual | Polite (です/ます) | Usage |
|--------|---------------|-------|
| 動く | 動きます | moves, operates |
| 返す | 返します | returns |
| クリックする | クリックします | clicks |
| 表示する | 表示します | displays |

### Common Pitfalls

- Avoid Hiragana-only text in technical documentation (use appropriate Kanji)
- Do not mix Katakana and Hiragana for the same foreign term inconsistently
- Maintain proper particle usage (を、に、で、から)
- Use polite form (ます/です) consistently in formal documentation

---

## Korean (한국어)

### Language Characteristics

- **Grammar**: Subject-Object-Verb (SOV); particles mark grammatical roles
- **Script**: Hangul (한글) - alphabetic system; 14 basic consonants and 10 basic vowels
- **Punctuation**: Korean periods (。) and commas (、); also uses English periods in mixed text
- **Spacing**: Spaces between word units (eojeol); typically one space after punctuation
- **Formality**: Honorific system; formal level (합니다 style) for technical writing
- **Particles**: Essential particles (를, 을, 이, 가) for grammatical relationships

### Writing Conventions

- **Headings**: Use "##" syntax; written in standard Korean
- **Hangul for native words**: Use Hangul for Korean words; Hanja (한자) for Chinese origin words where appropriate
- **English terms**: Can write English directly or use Hangul phonetic spelling (영어식 표기)
- **Formal style**: Use 합니다/습니다 verb endings for documentation
- **Code terminology**: Keep English terms directly or use phonetic Hangul equivalent
- **Lists**: Use "- " with proper indentation; commas separate items in lists

### Character Mapping (English to Korean)

| English | Korean (Hangul) | Alternative | Notes |
|---------|-----------------|-------------|-------|
| API | 에이피아이 | API (direct) | Application Programming Interface |
| Function | 함수 (漢數) | - | Mathematical/programming function |
| Parameter | 매개변수 | - | Function parameter |
| Return | 반환 | - | Return from function |
| Variable | 변수 (變數) | - | Programming variable |
| Library | 라이브러리 | - | Code library |
| Component | 컴포넌트 | - | UI component |

### Example Korean Text

```
# React 시작 가이드

React 는 재사용 가능한 컴포넌트를 사용하여 사용자 인터페이스를 구축하기 위한 JavaScript 라이브러리입니다.

## 설치

npm 또는 yarn 을 사용하여 React 를 설치합니다.

```bash
npm install react react-dom
```

## 첫 번째 컴포넌트 만들기

React 컴포넌트는 JSX 를 반환하는 JavaScript 함수입니다.

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```
```

### Formal Style Examples

| Casual | Formal (합니다) | Usage |
|--------|-------------|-------|
| 움직인다 | 움직입니다 | moves, operates |
| 돌려준다 | 돌려줍니다 | returns |
| 클릭한다 | 클릭합니다 | clicks |
| 표시한다 | 표시합니다 | displays |

### Particle Usage

- **를/을**: Object particle (직접 목적어)
- **이/가**: Subject particle (주어)
- **에**: Location/time particle (위치/시간)
- **의**: Possessive particle (소유)
- **도**: Also particle (도 함께)

### Common Pitfalls

- Do not mix Hangul and Hanja inconsistently
- Maintain formal verb endings (합니다/습니다) throughout
- Use proper particles (를, 을, 이, 가) for grammatical correctness
- Distinguish between Hangul phonetic spelling and English direct writing

---

## Indonesian (Bahasa Indonesia)

### Language Characteristics

- **Grammar**: Subject-Verb-Object (SVO); relatively simple grammar structure
- **Script**: Latin alphabet (a-z); no diacritical marks in standard writing
- **Punctuation**: Standard punctuation (. , ; :); spaces after punctuation
- **Spacing**: Spaces between all words; consistent spacing around code
- **Formality**: Levels of formality; formal writing (formal = baku) for technical documentation
- **Word formation**: Affixes (prefixes and suffixes) modify root words
- **Vocabulary**: Borrowings from Dutch, Arabic, and English; increasingly English terms in tech

### Writing Conventions

- **Headings**: Use "##" syntax; capitalize first word and proper nouns
- **English terms**: Often kept in English for technical terms (API, JavaScript, React)
- **Formality**: Use baku (standard formal) language; avoid colloquial forms
- **Affixes**: Use standard affixes for verbs (me-, -kan, -i, per-, -an)
- **Lists**: Use "- " with standard indentation
- **Active voice**: Strongly preferred in Indonesian technical writing

### Word Formation Examples

| Base Word | Affixed Form | Meaning |
|-----------|-----------|---------|
| instal | menginstal | to install |
| klik | mengklik | to click |
| jalankan | menjalankan | to run |
| kembalikan | mengembalikan | to return |
| tampilkan | menampilkan | to display |
| atur | mengatur | to configure |

### Character Mapping (English to Indonesian)

| English | Indonesian | Alternative | Notes |
|---------|------------|-----------|-------|
| API | API | Antarmuka Pemrograman Aplikasi | Usually kept as API in tech |
| Function | Fungsi | - | Programming function |
| Parameter | Parameter | - | Function parameter |
| Return | Kembali/Kembalikan | - | Return from function |
| Variable | Variabel | - | Programming variable |
| Library | Perpustakaan | Library (common in tech) | Code library |
| Component | Komponen | - | UI component |

### Example Indonesian Text

```
# Panduan Memulai React

React adalah perpustakaan JavaScript untuk membangun antarmuka pengguna dengan komponen yang dapat digunakan kembali.

## Instalasi

Untuk menginstal React, gunakan npm atau yarn:

```bash
npm install react react-dom
```

## Membuat Komponen Pertama

Komponen React adalah fungsi JavaScript yang mengembalikan JSX:

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```
```

### Affix Usage in Technical Writing

| Prefix | Example | Meaning |
|--------|---------|---------|
| me- | menginstal | to install |
| me- | mengkonfigurasi | to configure |
| -kan | kembalikan | return (command) |
| -i | atur | configure (command) |
| per- | perpustakaan | library (collection) |

### Common Pitfalls

- Do not use overly colloquial forms (avoid slang and regional dialects)
- Avoid mixing English and Indonesian randomly
- Maintain active voice (passive voice is uncommon in technical docs)
- Use consistent affixes for derived words
- Do not add English articles (a, the) within Indonesian text

---

## Cross-Language Considerations

### Terminology Consistency Across Languages

When managing documentation in multiple languages, maintain consistent term mapping:

| Concept | English | Simplified Chinese | Traditional Chinese | Japanese | Korean | Indonesian |
|---------|---------|------------------|------------------|----------|--------|-----------|
| Installation | Installation | 安装 | 安裝 | インストール | 설치 | Instalasi |
| Configuration | Configuration | 配置 | 設定 | 設定 | 구성 | Konfigurasi |
| Component | Component | 组件 | 元件 | コンポーネント | 컴포넌트 | Komponen |
| API | API | 应用程序接口 | 應用程式介面 | API | API | API |
| Function | Function | 函数 | 函式 | 関数 | 함수 | Fungsi |

### Managing Glossaries

Maintain a master glossary with entries for each term and its translations:

```json
{
  "glossary_entry": {
    "english": "Definition in English",
    "zh": "简体中文",
    "zh_tw": "繁體中文",
    "ja": "日本語",
    "ko": "한국어",
    "id": "Bahasa Indonesia",
    "context": "Where/when to use this term",
    "technical_level": "beginner|intermediate|advanced"
  }
}
```

### Formatting Conventions by Language

| Aspect | English | Chinese | Japanese | Korean | Indonesian |
|--------|---------|---------|----------|--------|-----------|
| Spaces around operators | `a + b` | `a+b` | `a + b` | `a + b` | `a + b` |
| Code terminology | English | Keep English | Katakana + English | Hangul or English | English |
| Parentheses spacing | `function()` | `函数()` | `関数()` | `함수()` | `fungsi()` |
| Quotation marks | "text" | 「文本」 | 「テキスト」 | "텍스트" | "teks" |

### Cultural & Contextual Differences

Different regions may have different conventions for:
- Date and time formats (2024-03-18 vs 18/03/2024 vs 2024年3月18日)
- Number formatting (1,000.00 vs 1.000,00 vs 1,000)
- Measurement units (metric vs imperial)
- Holiday and timezone references
- Business day definitions

When translating time-sensitive or region-specific content, adjust for local conventions.

---

## Best Practices for Multilingual Translation

1. **Start with a clear glossary**: Define all technical terms and their translations before beginning translation work
2. **Use consistent terminology**: Reference the glossary throughout to ensure the same English term always translates to the same target term
3. **Maintain formatting**: Preserve code blocks, links, and emphasis exactly as they appear
4. **Test translations**: Run translations through validators and have native speakers review critical content
5. **Update iteratively**: After each translation, update your glossaries with new terms and corrections
6. **Consider context**: Technical documentation has different conventions than marketing material
7. **Respect language rules**: Follow each language's grammar and punctuation conventions, not English patterns
8. **Handle cultural differences**: Adapt examples and references to be culturally appropriate for target audiences

---

## Language-Specific Validation Checklist

### Chinese Validation

- [ ] No spaces between Chinese characters (except around code)
- [ ] Proper Chinese punctuation marks used (。 ， ： ；)
- [ ] Simplified OR Traditional (not mixed)
- [ ] English terms marked with brackets if necessary
- [ ] No unnecessary quotation marks

### Japanese Validation

- [ ] Appropriate use of Hiragana, Katakana, and Kanji
- [ ] Foreign terms in Katakana
- [ ] Polite verb forms (ます/です) used consistently
- [ ] Proper particle usage
- [ ] No English articles inserted in Japanese text

### Korean Validation

- [ ] Correct Hangul spelling throughout
- [ ] Proper particle usage (를, 을, 이, 가)
- [ ] Formal verb endings (합니다/습니다) used
- [ ] Consistent Hanja usage or Hangul alternatives
- [ ] Appropriate spacing between word units

### Indonesian Validation

- [ ] Correct affix usage for verbs
- [ ] Active voice maintained
- [ ] Consistent formal language (avoid colloquialisms)
- [ ] Proper spacing between all words
- [ ] English technical terms used appropriately

