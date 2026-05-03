# Wiki API Documentation

Guide for integrating frontend applications with the Wiki system powered by LLM.

---

## Overview

The Wiki system implements Karpathy's LLM-powered personal knowledge base pattern:
- **Raw sources** are ingested and processed by LLM
- **Wiki pages** are auto-generated with summaries, entities, and cross-references
- **LLM queries** provide contextual answers from accumulated knowledge

**Architecture**:
- **Multi-Tenant**: Each hotel (tenant) has isolated wiki data via `tenant_id`
- **Shared API Keys**: OpenRouter key is shared across all tenants (configured in env)
- **LLM-Powered**: Uses shared OpenRouter API key for all LLM operations

---

## Authentication

All wiki endpoints require JWT authentication with tenant_id. Include the access token in the `Authorization` header:

```
Authorization: Bearer <access_token>  # Contains tenant_id in JWT payload
```

---

## Endpoints

### Ingest Source

Add a new source to the wiki. The LLM will generate summaries, extract entities, and create related pages.

**Endpoint**: `POST /wiki/ingest`

**Request Body**:
```json
{
  "title": "Article Title",
  "source_type": "article",
  "content": "Full content of the source...",
  "url": "https://original-source-url.com",
  "tags": ["tag1", "tag2"],
  "extra_data": {"author": "Name"},
  "generate_summary": true,
  "create_entity_pages": true
}
```

**Response** (201 Created):
```json
{
  "source": {
    "id": "uuid",
    "title": "Article Title",
    "source_type": "article",
    "summary": "LLM-generated summary...",
    "is_processed": true,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "created_pages": [...],
  "updated_pages": [],
  "log_entry_id": "uuid"
}
```

---

### Query Wiki

Ask questions and get LLM-powered answers based on the wiki content.

**Endpoint**: `POST /wiki/query`

**Request Body**:
```json
{
  "question": "What amenities does the hotel offer?",
  "context": "Optional additional context"
}
```

**Response**:
```json
{
  "answer": "The hotel offers a swimming pool, spa, and restaurant...",
  "citations": [
    {
      "page_title": "Hotel Amenities",
      "excerpt": "Our hotel features..."
    }
  ],
  "related_pages": [...]
}
```

---

### Get Wiki Index

Get overview statistics of the wiki.

**Endpoint**: `GET /wiki/index`

**Response**:
```json
{
  "total_pages": 42,
  "total_sources": 15,
  "categories": {
    "entity": 20,
    "concept": 15,
    "note": 7
  },
  "recent_pages": [...],
  "recent_sources": [...]
}
```

---

### List Sources

List all ingested sources.

**Endpoint**: `GET /wiki/sources?skip=0&limit=50`

**Response**:
```json
{
  "sources": [
    {
      "id": "uuid",
      "title": "Source Title",
      "source_type": "article",
      "summary": "Brief summary...",
      "tags": ["tag1", "tag2"],
      "is_processed": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 15
}
```

---

### List Pages

List all wiki pages.

**Endpoint**: `GET /wiki/pages?skip=0&limit=50`

**Response**:
```json
{
  "pages": [
    {
      "id": "uuid",
      "title": "Page Title",
      "page_type": "entity",
      "slug": "page-title",
      "summary": "Brief summary...",
      "content": "Full page content...",
      "tags": ["tag1"],
      "is_draft": false,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 42
}
```

---

### Search Pages

Search wiki pages by query.

**Endpoint**: `GET /wiki/pages/search?q=query&limit=10`

**Response**:
```json
{
  "pages": [...],
  "total": 3
}
```

---

## Source Types

| Type | Description |
|------|-------------|
| `article` | Web article or blog post |
| `document` | PDF or document file |
| `faq` | Frequently asked questions |
| `policy` | Hotel policies |
| `note` | Internal notes |
| `other` | Uncategorized |

---

## Page Types

| Type | Description |
|------|-------------|
| `entity` | Person, place, or thing |
| `concept` | Abstract concept or idea |
| `source` | Generated from a source |
| `note` | Internal note |

---

## Error Handling

| Status | Meaning |
|--------|---------|
| 400 | Invalid request body |
| 401 | Missing or invalid token |
| 404 | Resource not found |
| 500 | Server error (LLM failure, etc.) |

---

## Rate Limiting

No rate limiting currently enforced. LLM calls are debounced server-side.
