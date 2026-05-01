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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | Yes | Source title |
| source_type | enum | No | article, paper, book, video, podcast, note, webpage, other |
| content | string | Yes | Full content |
| url | string | No | Original source URL |
| tags | array | No | Tags for categorization |
| extra_data | object | No | Additional metadata |
| generate_summary | boolean | No | Enable LLM summary (default: true) |
| create_entity_pages | boolean | No | Auto-create entity pages (default: true) |

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
  "created_pages": [
    {
      "id": "uuid",
      "title": "Article Title",
      "page_type": "source",
      "slug": "article-title"
    }
  ],
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
  "question": "What is machine learning?",
  "context": "Optional additional context",
  "max_pages": 10
}
```

**Response** (200 OK):
```json
{
  "answer": "Machine learning is a subset of AI that enables systems to learn...",
  "citations": [
    {
      "page_title": "Machine Learning",
      "page_id": "uuid",
      "excerpt": "A subset of artificial intelligence..."
    }
  ],
  "related_pages": [
    {"id": "uuid", "title": "Machine Learning", ...}
  ]
}
```

---

### Lint Wiki

Run health checks on the wiki to find issues.

**Endpoint**: `POST /wiki/lint`

**Request Body**:
```json
{
  "check_contradictions": true,
  "check_orphans": true,
  "check_stale": true,
  "check_links": true
}
```

**Response** (200 OK):
```json
{
  "issues": [
    {
      "issue_type": "orphan",
      "description": "Page has no incoming links",
      "affected_pages": ["page-title"],
      "suggestion": "Add cross-references to this page"
    }
  ],
  "stats": {
    "total_pages": 50,
    "total_sources": 10,
    "orphan_count": 3
  }
}
```

---

### Get Index

Get overview of the entire wiki.

**Endpoint**: `GET /wiki/index`

**Response** (200 OK):
```json
{
  "total_pages": 50,
  "total_sources": 10,
  "categories": {
    "entity": 15,
    "concept": 5,
    "source": 10,
    "summary": 3,
    "note": 17
  },
  "recent_pages": [...],
  "recent_sources": [...]
}
```

---

### Sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/wiki/sources` | List all sources (paginated) |
| GET | `/wiki/sources/{id}` | Get source details |

---

### Pages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/wiki/pages` | List all pages (paginated) |
| GET | `/wiki/pages/search?q=query` | Search pages |
| GET | `/wiki/pages/{id}` | Get page by ID |
| GET | `/wiki/pages/slug/{slug}` | Get page by slug |
| POST | `/wiki/pages` | Create new page |
| PATCH | `/wiki/pages/{id}` | Update page |
| DELETE | `/wiki/pages/{id}` | Delete page |

---

### Log

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/wiki/log` | Get operation log |

---

## Integration Examples

### JavaScript (fetch)

```javascript
const API_BASE = 'http://localhost:8000';

// Get auth token first
const login = async () => {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'user@example.com', password: 'password' })
  });
  const { access_token } = await response.json();
  localStorage.setItem('access_token', access_token);
  return access_token;
};

const headers = () => ({
  'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
  'Content-Type': 'application/json'
});

// Ingest a source
const ingestSource = async (title, content, tags) => {
  const response = await fetch(`${API_BASE}/wiki/ingest`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      title,
      source_type: 'article',
      content,
      tags
    })
  });
  return response.json();
};

// Query the wiki
const queryWiki = async (question) => {
  const response = await fetch(`${API_BASE}/wiki/query`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ question })
  });
  return response.json();
};

// Search pages
const searchPages = async (query) => {
  const response = await fetch(`${API_BASE}/wiki/pages/search?q=${encodeURIComponent(query)}`, {
    headers: headers()
  });
  return response.json();
};
```

### Python (requests)

```python
import requests

API_BASE = 'http://localhost:8000'

def get_token(email, password):
    response = requests.post(f'{API_BASE}/auth/login', json={
        'email': email,
        'password': password
    })
    return response.json()['access_token']

token = get_token('user@example.com', 'password')
headers = {'Authorization': f'Bearer {token}'}

# Ingest
def ingest(title, content, tags):
    return requests.post(f'{API_BASE}/wiki/ingest', headers=headers, json={
        'title': title,
        'source_type': 'article',
        'content': content,
        'tags': tags
    }).json()

# Query
def query(question):
    return requests.post(f'{API_BASE}/wiki/query', headers=headers, json={
        'question': question
    }).json()

# Search
def search(query):
    return requests.get(f'{API_BASE}/wiki/pages/search?q={query}', headers=headers).json()
```

---

## Page Types

| Type | Description |
|------|-------------|
| `source` | Summary page for an ingested source |
| `entity` | Person, place, organization, or thing |
| `concept` | Abstract ideas and topics |
| `summary` | High-level synthesis of multiple sources |
| `note` | User-created notes and annotations |

---

## Wiki Link Format

Internal links use double bracket syntax:
```
[[Page Title]]
```

These links are automatically tracked and enable:
- Cross-referencing between pages
- Graph visualization of connections
- Finding related content

---

## Error Handling

| Status | Error | Solution |
|--------|-------|----------|
| 400 | Invalid source type | Use valid source_type enum |
| 401 | Not authenticated | Login and include token |
| 404 | Page/Source not found | Check ID or slug |
| 422 | Validation error | Check request body format |
| 500 | LLM error | Check OpenRouter API key |

---

## LLM Processing Notes

When ingesting sources:
1. Source is saved to `wiki/sources/`
2. LLM generates a summary
3. Entities are extracted and entity pages created
4. Cross-references are established
5. Operation is logged

Processing is synchronous by default. For large sources, consider:
- Reducing content length
- Disabling entity extraction
- Using batch ingestion

---

## File Storage

Wiki files are stored in:
- `wiki/sources/` - Raw source documents
- `wiki/pages/` - Generated wiki pages (organized by type)
- `wiki/assets/` - Downloaded images and files

Markdown files in `wiki/pages/` can be:
- Edited directly
- Synced with Obsidian
- Version controlled with git