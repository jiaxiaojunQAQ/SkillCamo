# Translation Examples

This document provides practical examples of how the markdown-multilingual-translator handles content in all six languages. Each example shows the input Markdown and its translation into other languages while preserving code blocks, links, and formatting.

## Example 1: Simple Guide

### Source (English)

```markdown
# Getting Started with React

React is a JavaScript library for building user interfaces.

## Installation

To install React, run this command:

```bash
npm install react react-dom
```

## Your First Component

A React component is a JavaScript function:

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```

You can use this component in your application by rendering it with `ReactDOM.render()`.
```

### Translated to Simplified Chinese (中文 - 简体)

```markdown
# React 入门指南

React 是一个用于构建用户界面的 JavaScript 库。

## 安装

要安装 React，请运行以下命令：

```bash
npm install react react-dom
```

## 你的第一个组件

React 组件是一个 JavaScript 函数：

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```

你可以通过使用 `ReactDOM.render()` 在你的应用中使用这个组件。
```

**Key observations:**
- Code block (```bash, ```javascript) preserved exactly
- Command `npm install react react-dom` not translated
- Inline code `ReactDOM.render()` preserved (no translation)
- Text headings and paragraphs translated
- No spaces added around Chinese text

### Translated to Taiwan Traditional Chinese (繁體中文)

```markdown
# React 入門指南

React 是一個用於構建使用者介面的 JavaScript 程式庫。

## 安裝

要安裝 React，請執行以下命令：

```bash
npm install react react-dom
```

## 你的第一個元件

React 元件是一個 JavaScript 函式：

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```

你可以透過使用 `ReactDOM.render()` 在你的應用程式中使用這個元件。
```

**Key observations:**
- Uses Taiwan-specific terminology (軟體, 元件, 程式庫 instead of Simplified equivalents)
- Grammar patterns reflect Taiwan usage
- Formal level maintained

### Translated to Japanese (日本語)

```markdown
# React 入門ガイド

React は、ユーザー インターフェースを構築するための JavaScript ライブラリです。

## インストール

React をインストールするには、このコマンドを実行します：

```bash
npm install react react-dom
```

## 最初のコンポーネント

React コンポーネントは、JavaScript 関数です：

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```

`ReactDOM.render()` を使用して、アプリケーションでこのコンポーネントを使用できます。
```

**Key observations:**
- Foreign terms in Katakana (ガイド, インストール, ライブラリ, コンポーネント)
- Polite form (です) maintained throughout
- Code blocks preserved
- Inline code preserved

### Translated to Korean (한국어)

```markdown
# React 시작 가이드

React 는 사용자 인터페이스를 구축하기 위한 JavaScript 라이브러리입니다.

## 설치

React 를 설치하려면 이 명령을 실행합니다.

```bash
npm install react react-dom
```

## 첫 번째 컴포넌트

React 컴포넌트는 JavaScript 함수입니다.

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```

`ReactDOM.render()` 를 사용하여 응용 프로그램에서 이 컴포넌트를 사용할 수 있습니다.
```

**Key observations:**
- Formal verb endings (습니다) used
- Spaces after particles (를, 는, 에서)
- Code and inline code preserved
- Proper Hangul spacing maintained

### Translated to Indonesian (Bahasa Indonesia)

```markdown
# Panduan Memulai React

React adalah perpustakaan JavaScript untuk membangun antarmuka pengguna.

## Instalasi

Untuk memasang React, jalankan perintah ini:

```bash
npm install react react-dom
```

## Komponen Pertama Anda

Komponen React adalah fungsi JavaScript:

```javascript
function Hello() {
  return <h1>Hello, World!</h1>;
}
```

Anda dapat menggunakan komponen ini di aplikasi Anda dengan merender dengan `ReactDOM.render()`.
```

**Key observations:**
- Active voice maintained (Anda dapat menggunakan)
- Formal language (memasang instead of pasang)
- Code blocks preserved
- Affixes used correctly (memasang, merender)

---

## Example 2: API Documentation with Tables

### Source (English)

```markdown
# Authentication API

## Overview

The Authentication API provides secure access to your application resources. All requests must include valid credentials.

## HTTP Methods

| Method | Purpose | Example |
|--------|---------|---------|
| GET | Retrieve data | `/api/users` |
| POST | Create data | `/api/users/create` |
| PUT | Update data | `/api/users/123` |

## Error Codes

When authentication fails, the API returns error codes:

- **401 Unauthorized**: Missing or invalid credentials
- **403 Forbidden**: Valid credentials but insufficient permissions
- **500 Internal Server Error**: Server-side issue

## Example Request

```bash
curl -X GET https://api.example.com/users \
  -H "Authorization: Bearer TOKEN"
```

## Response Format

Successful responses return JSON:

```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "John Doe"
  }
}
```
```

### Translated to Simplified Chinese (中文 - 简体)

```markdown
# 身份验证 API

## 概述

身份验证 API 为你的应用资源提供安全访问。所有请求必须包含有效的凭据。

## HTTP 方法

| 方法 | 目的 | 示例 |
|------|------|------|
| GET | 检索数据 | `/api/users` |
| POST | 创建数据 | `/api/users/create` |
| PUT | 更新数据 | `/api/users/123` |

## 错误代码

当身份验证失败时，API 返回错误代码：

- **401 Unauthorized**: 缺少或无效的凭据
- **403 Forbidden**: 有效的凭据但权限不足
- **500 Internal Server Error**: 服务器端问题

## 示例请求

```bash
curl -X GET https://api.example.com/users \
  -H "Authorization: Bearer TOKEN"
```

## 响应格式

成功的响应返回 JSON：

```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "John Doe"
  }
}
```
```

**Key observations:**
- Table structure and URLs preserved
- Error codes (401, 403, 500) not translated
- Code blocks (bash, json) preserved completely
- HTTP method names (GET, POST, PUT) kept in English
- API endpoint paths not translated

### Translated to Japanese (日本語)

```markdown
# 認証 API

## 概要

認証 API は、アプリケーション リソースへの安全なアクセスを提供します。すべてのリクエストには有効な認証情報を含める必要があります。

## HTTP メソッド

| メソッド | 目的 | 例 |
|---------|------|-----|
| GET | データを取得する | `/api/users` |
| POST | データを作成する | `/api/users/create` |
| PUT | データを更新する | `/api/users/123` |

## エラー コード

認証に失敗すると、API はエラー コードを返します：

- **401 Unauthorized**: 認証情報がないか無効です
- **403 Forbidden**: 有効な認証情報ですが、権限が不足しています
- **500 Internal Server Error**: サーバー側の問題

## 要求の例

```bash
curl -X GET https://api.example.com/users \
  -H "Authorization: Bearer TOKEN"
```

## 応答形式

成功した応答は JSON を返します：

```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "John Doe"
  }
}
```
```

---

## Example 3: Configuration Guide with Lists

### Source (English)

```markdown
# Configuration Guide

## Setting Up Your Environment

Before you begin, ensure you have:

1. Node.js version 14 or higher
2. npm or yarn package manager
3. A text editor (VS Code recommended)
4. Git for version control

## Configuration File

Create a file named `config.json`:

```json
{
  "api_url": "https://api.example.com",
  "timeout": 30000,
  "retry_attempts": 3,
  "debug": false
}
```

## Environment Variables

Set these environment variables:

- `API_KEY`: Your authentication key
- `NODE_ENV`: Set to `production` or `development`
- `LOG_LEVEL`: Set to `info`, `warn`, or `error`

## Troubleshooting

If you encounter issues:

1. Check your configuration file is valid JSON
2. Verify all required environment variables are set
3. Review logs at `/var/log/app.log`
4. Contact support if problems persist
```

### Translated to Korean (한국어)

```markdown
# 구성 가이드

## 환경 설정

시작하기 전에 다음을 확인하세요:

1. Node.js 버전 14 이상
2. npm 또는 yarn 패키지 관리자
3. 텍스트 편집기 (VS Code 권장)
4. 버전 제어용 Git

## 구성 파일

`config.json` 이라는 파일을 만듭니다:

```json
{
  "api_url": "https://api.example.com",
  "timeout": 30000,
  "retry_attempts": 3,
  "debug": false
}
```

## 환경 변수

다음 환경 변수를 설정합니다:

- `API_KEY`: 인증 키
- `NODE_ENV`: `production` 또는 `development` 로 설정
- `LOG_LEVEL`: `info`, `warn` 또는 `error` 로 설정

## 문제 해결

문제가 발생하면:

1. 구성 파일이 유효한 JSON 인지 확인
2. 필요한 모든 환경 변수가 설정되어 있는지 확인
3. `/var/log/app.log` 에서 로그 검토
4. 문제가 지속되면 지원팀에 문의하세요
```

**Key observations:**
- Numbered and bulleted lists preserved
- File name `config.json` kept in English
- JSON code block unchanged
- Environment variable names kept as-is
- File path `/var/log/app.log` not translated
- Parenthetical recommendations translated

### Translated to Indonesian (Bahasa Indonesia)

```markdown
# Panduan Konfigurasi

## Menyiapkan Lingkungan Anda

Sebelum Anda mulai, pastikan Anda memiliki:

1. Node.js versi 14 atau lebih tinggi
2. npm atau yarn manajer paket
3. Editor teks (VS Code disarankan)
4. Git untuk kontrol versi

## File Konfigurasi

Buat file bernama `config.json`:

```json
{
  "api_url": "https://api.example.com",
  "timeout": 30000,
  "retry_attempts": 3,
  "debug": false
}
```

## Variabel Lingkungan

Atur variabel lingkungan ini:

- `API_KEY`: Kunci otentikasi Anda
- `NODE_ENV`: Atur ke `production` atau `development`
- `LOG_LEVEL`: Atur ke `info`, `warn`, atau `error`

## Penyelesaian Masalah

Jika Anda mengalami masalah:

1. Periksa file konfigurasi Anda adalah JSON yang valid
2. Verifikasi semua variabel lingkungan yang diperlukan sudah diatur
3. Tinjau log di `/var/log/app.log`
4. Hubungi dukungan jika masalah terus berlanjut
```

---

## Example 4: Multilingual FAQ

This example shows how terminology remains consistent across languages:

### Question in Multiple Languages

**English:**
```
Q: What is an API endpoint?
A: An API endpoint is a specific URL where an API can be accessed.
```

**Simplified Chinese:**
```
问：什么是 API 端点？
答：API 端点是一个可以访问 API 的特定 URL。
```

**Taiwan Traditional Chinese:**
```
問：什麼是 API 端點？
答：API 端點是一個可以存取 API 的特定 URL。
```

**Japanese:**
```
Q: API エンドポイント とは何ですか?
A: API エンドポイント は、API にアクセスできる特定の URL です。
```

**Korean:**
```
Q: API 엔드포인트 란 무엇입니까?
A: API 엔드포인트 는 API 에 액세스할 수 있는 특정 URL 입니다.
```

**Indonesian:**
```
T: Apa itu titik akhir API?
J: Titik akhir API adalah URL tertentu tempat API dapat diakses.
```

**Key observations:**
- English term "API endpoint" consistently translated as:
  - Chinese: "API 端点" or "API 端點"
  - Japanese: "API エンドポイント"
  - Korean: "API 엔드포인트"
  - Indonesian: "titik akhir API"
- Terminology consistency across all languages
- English acronyms (API, URL) preserved in all versions

---

## Example 5: Complex Structure with Nested Lists

### Source (English)

```markdown
# Project Structure

## File Organization

Your project should follow this structure:

- `src/` - Source code directory
  - `components/` - React components
    - `Button.js`
    - `Header.js`
  - `pages/` - Page components
    - `Home.js`
    - `About.js`
  - `utils/` - Utility functions
    - `api.js`
    - `helpers.js`
- `public/` - Static assets
  - `index.html`
  - `favicon.ico`
- `package.json` - Project configuration
- `README.md` - Documentation
```

### Translated to Traditional Chinese (繁體中文)

```markdown
# 項目結構

## 文件組織

你的項目應該遵循此結構：

- `src/` - 原始碼目錄
  - `components/` - React 元件
    - `Button.js`
    - `Header.js`
  - `pages/` - 頁面元件
    - `Home.js`
    - `About.js`
  - `utils/` - 實用程式函數
    - `api.js`
    - `helpers.js`
- `public/` - 靜態資源
  - `index.html`
  - `favicon.ico`
- `package.json` - 專案配置
- `README.md` - 文件
```

**Key observations:**
- File paths and file names preserved (`.js`, `.html`, `.json`, `.md`)
- Directory names preserved as-is
- Directory descriptions translated
- Nested list structure perfectly maintained
- Indentation preserved

---

## Translation Quality Metrics

These examples demonstrate the expected quality levels:

| Aspect | Expected Quality |
|--------|------------------|
| **Code preservation** | 100% - No code changes |
| **Link/URL preservation** | 100% - URLs unchanged |
| **Structure preservation** | 100% - Markdown structure identical |
| **Terminology consistency** | 95%+ - Uses glossary for consistent terms |
| **Grammar accuracy** | 90%+ - Native grammar rules followed |
| **Technical accuracy** | 95%+ - Technical concepts preserved |
| **Cultural appropriateness** | 90%+ - Respects regional conventions |

---

## Tips for Best Results

1. **Use glossaries**: Reference materials ensure consistent terminology
2. **Review examples**: Check examples in your target language before translating large documents
3. **Test with small samples**: Verify quality with a small portion before full translation
4. **Validate output**: Always validate translated files for structure integrity
5. **Get native review**: Have native speakers review critical or customer-facing content
6. **Iterate and improve**: Update glossaries based on translation results

