# Wiki LLM Agent Schema

This schema defines how the LLM agent should operate when maintaining the wiki.

## Overview

The wiki is a persistent, compounding knowledge base. It consists of:
- **Raw Sources**: Immutable source documents (articles, papers, notes)
- **Wiki Pages**: LLM-generated markdown files with summaries, entities, concepts
- **Index**: Catalog of all wiki pages
- **Log**: Chronological record of all operations

## Directory Structure

```
wiki/
├── sources/          # Raw source documents (immutable)
├── pages/            # LLM-generated wiki pages
│   ├── entities/      # Entity pages (people, places, concepts)
│   ├── concepts/      # Concept pages (topics, ideas)
│   ├── sources/       # Source summary pages
│   ├── summaries/     # Overview/synthesis pages
│   └── notes/         # Ad-hoc notes and analyses
├── assets/           # Downloaded images and files
├── index.md          # Wiki catalog
└── log.md            # Operation log
```

## Page Template

Every wiki page should follow this structure:

```markdown
---
title: Page Title
type: entity|concept|source|summary|note
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [tag1, tag2]
sources: [source1, source2]
---

# Page Title

## Summary
Brief overview of the page content.

## Details
Detailed content...

## Related
- [[Related Page 1]]
- [[Related Page 2]]
```

## Naming Conventions

- Filenames: lowercase-with-hyphens.md (e.g., `attention-mechanism.md`)
- Internal links: `[[Page Title]]` format
- Tags: lowercase, hyphenated (e.g., `machine-learning`, `research`)
- Sources: quoted with context (e.g., `"Attention is All You Need"`)

## Operations

### Ingest

When adding a new source:

1. Copy source file to `wiki/sources/`
2. Read and analyze the source
3. Create/update relevant entity and concept pages
4. Update the source summary page in `pages/sources/`
5. Update `index.md` with new pages
6. Append entry to `log.md`

### Query

When answering a question:

1. Read `index.md` to find relevant pages
2. Read relevant pages
3. Synthesize answer with citations
4. Optionally save answer as a new note page

### Lint

Periodically:

1. Check for contradictions between pages
2. Find stale claims superseded by newer sources
3. Identify orphan pages with no inbound links
4. Note missing cross-references
5. Suggest new questions and sources to investigate

## Wiki Health Checklist

- [ ] All pages have proper frontmatter
- [ ] Internal links are valid (pages exist)
- [ ] No contradictions with recent sources
- [ ] Index reflects actual page count
- [ ] Log is up to date

## Styling Guidelines

- Use `##` for main sections, `###` for subsections
- Keep pages focused (one topic per page)
- Cross-reference liberally
- Include citations for claims
- Use bullet points for lists
- Keep summaries at the top

## Notes

- Never modify raw source files
- Always log operations in log.md
- Update index.md after every change
- Use consistent date format (YYYY-MM-DD)