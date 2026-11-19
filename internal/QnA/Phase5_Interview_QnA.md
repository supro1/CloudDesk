# Phase 5 — Interview Questions and Answers

This question bank covers Phase 5: CloudDesk's knowledge articles, chunking,
offline embeddings, vector storage, hybrid retrieval, ingestion, and knowledge
API. The answers are designed for a mixed technical and non-technical
interview board. They describe what is implemented and distinguish it from
later-phase or production work.

## Product and phase overview

### 1. What was the goal of Phase 5?

To turn support documentation into a searchable knowledge library and expose
that library through authenticated API routes.

### 2. How would you explain Phase 5 to a non-technical person?

I organized the support team's help articles so staff can quickly find a
relevant, traceable passage instead of manually searching every document. The
system returns the passage and its source article so staff can verify it.

### 3. What analogy would you use?

It is like building a library catalog. The articles are books, the chunks are
labeled passages, the index helps locate relevant passages, and a citation
points back to the original page or section.

### 4. What are the four Phase 5 tasks?

P5-1 validates and chunks knowledge articles. P5-2 adds offline embeddings
and interchangeable vector storage. P5-3 combines keyword and vector search.
P5-4 adds ingestion and authenticated knowledge API routes.

### 5. Is Phase 5 an AI support agent?

No. It builds the retrieval capability that a later knowledge agent can use.
It does not classify or resolve tickets, decide policy, or send customer
replies.

### 6. What can you confidently say is implemented?

Markdown article loading and validation, deterministic fake embeddings,
in-memory and Qdrant vector-store implementations, hybrid retrieval, a
database-backed ingestion service and command, and authenticated list,
detail, search, and admin-only reindex endpoints.

## Articles, metadata, and chunking

### 7. Where do the articles come from?

They are Markdown files under `sample_data/knowledge_base/`. The directory is
selected through `SAMPLE_DATA_DIR`, which defaults to `sample_data`.

### 8. What is in an article's front matter?

The loader requires a title, a recognized ticket category, a summary, and a
list of non-empty tags. The article body must also be present.

### 9. Why validate article files before indexing them?

Bad metadata can cause unreliable filtering or incomplete citations. Failing
early with a clear file-specific error is safer than quietly indexing a
partially understood document.

### 10. What is a chunk?

A chunk is a smaller passage cut from a larger article. It is the unit the
search system ranks and returns as evidence.

### 11. How does chunking work?

The chunker first splits content at Markdown headings, then divides longer
sections into windows up to 900 characters with 150 characters of overlap.
The overlap reduces the chance that context is lost at a boundary.

### 12. Why split by headings before using fixed-size windows?

Headings provide meaningful section boundaries. Keeping a heading in each
chunk makes the result easier to understand and cite than an arbitrary
character slice alone.

### 13. Why overlap chunks?

Important context may span the end of one window and the start of the next.
Overlap lets both passages retain some of that neighboring context.

### 14. How does a search result link back to its source?

Each chunk stores the article slug and a heading-based source such as
`kb://mfa-account-recovery#recovery`. The returned evidence also includes an
article URL like `/knowledge/mfa-account-recovery`.

### 15. How are chunk IDs made stable?

The chunk ID is based on the article slug, section position, and window
position. Reprocessing an unchanged article therefore produces the same
identifiers. If the article structure changes, affected IDs can change too.

### 16. Are published articles the same as indexed chunks?

No. The SQL article record is the canonical article content and metadata.
Chunks and vectors are a derived search index that can be rebuilt from the
published article records.

## Embeddings and vector storage

### 17. What is an embedding?

An embedding is a list of numbers representing text in a form that a vector
search can compare. Here it is one input to similarity search.

### 18. Which embedding implementation is active?

The current path uses `FakeEmbeddings`, a deterministic hash-based bag of
words. It permits offline development and repeatable tests without an API
key.

### 19. Are the fake embeddings equivalent to a language model?

No. They do not understand meaning like a trained embedding model. They are a
lightweight stand-in for development, and results should not be represented as
production semantic quality.

### 20. Why use fake embeddings?

They make the knowledge pipeline testable offline, avoid external API costs,
and keep results deterministic. The vector-store protocol makes it possible
to change the implementation later.

### 21. What is a vector store?

It is storage for passage vectors and their metadata, with a way to search
those vectors by similarity.

### 22. Which vector-store choices exist?

`InMemoryVectorStore` is the default local option. `QdrantVectorStore` is
available when `VECTOR_STORE=qdrant` and a valid `QDRANT_URL` is configured.

### 23. What does the vector-store protocol buy us?

It defines a common set of operations such as adding documents, searching,
deleting, clearing, counting, and checking health. The retriever can use that
interface without knowing whether the data is in memory or Qdrant.

### 24. Is the in-memory index durable?

No. It disappears when the process ends. Article content persists in SQL, so
the API can reconstruct the index when it needs it. A configured external
vector store is a separate persistence option.

### 25. What happens if vector dimensions do not match?

The vector store validates dimensions and rejects incompatible vectors. This
prevents queries and stored data from being compared using mismatched vector
formats.

### 26. Is Qdrant running in Docker as part of this phase?

No. The code can connect to a configured Qdrant URL, but Phase 5 does not add
a Docker Compose file or provision a Qdrant service.

## Retrieval and citations

### 27. What is hybrid retrieval?

It combines two ways to find useful passages: matching words in the text and
comparing numeric vector representations. It then merges the rankings.

### 28. What is the difference between keyword, semantic, and hybrid modes?

Keyword mode uses the BM25 keyword index. Semantic mode uses vector
similarity. Hybrid mode uses both and combines their ranks.

### 29. What is BM25?

It is a standard keyword-scoring method that estimates how well a document
matches query terms, taking into account term frequency and how common those
terms are across the collection.

### 30. How are the two ranked lists combined?

The retriever uses reciprocal-rank fusion. Instead of assuming BM25 scores
and vector scores share the same scale, it uses each result's position in its
ranked list to calculate a combined score.

### 31. Why not just add the BM25 and vector scores?

The two systems produce scores with different meanings and ranges. Combining
their ranks avoids treating those raw scores as directly comparable.

### 32. Does category filtering work for every retrieval mode?

Yes. The category is applied to vector search and keyword filtering, and
results are checked again during ranking. A small category-match boost is
also applied when a category was provided.

### 33. Why return only one chunk per article?

Without deduplication, one long article could occupy most of the top results.
Keeping the best passage per article gives the user a more varied set of
sources.

### 34. What is in an evidence result?

It includes a chunk ID, title, citation source, short snippet, relevance
score, article URL, and article ID. This is enough for the caller to show the
reason for a result and let a user inspect the article.

### 35. Is the reranker active?

There is an optional reranker interface, but no external or language-model
reranker is configured in this phase. I would describe it as an extension
point, not as an active capability.

### 36. What happens when no search results match?

The API returns the query with an empty `items` list. It does not invent an
article or fabricate a citation.

## Ingestion and API

### 37. What does `make ingest` do?

It runs `python -m rag.ingest`. The command loads and validates the Markdown
files, upserts their article records, unpublishes removed source files,
chunks the published content, creates embeddings, and replaces the configured
vector index.

### 38. Why keep both the Markdown source and SQL article records?

Markdown is a convenient editable source for the team. SQL provides
application-level persistence and lets the API list and retrieve articles.
The vector index is derived and can be rebuilt from the stored article data.

### 39. What does reindexing mean here?

It reloads the configured Markdown source, synchronizes article records, and
replaces the configured vector collection from the published articles. It
removes stale indexed passages rather than merely adding more copies.

### 40. Which knowledge API endpoints exist?

`GET /api/v1/knowledge` lists published articles; `GET
/api/v1/knowledge/{article_id}` returns one published article; `POST
/api/v1/knowledge/search` searches; and `POST
/api/v1/knowledge/reindex` refreshes the source and index.

### 41. What are the access rules?

Any authenticated role can browse, read, and search. Reindexing requires the
admin role because it replaces the shared search index and synchronizes
content.

### 42. What options can be sent to search?

The request includes a non-blank query, optional category, a mode
(`hybrid`, `semantic`, or `keyword`), and `top_k` from 1 through 20. The
defaults are hybrid mode and three results.

### 43. Does a list endpoint return every article at once?

No. It supports `limit` and `offset` pagination and returns a total count with
the selected page.

### 44. Can an unpublished article be read through the API?

No. The detail endpoint returns `404` for an unpublished article or an unknown
ID, which avoids presenting drafts as approved support material.

### 45. How does the API know whether its in-memory index is stale?

The service compares a signature of published article IDs, slugs, timestamps,
and content with the signature used for the current index. If the set changes,
it rebuilds the index before searching.

### 46. Does article reindexing happen automatically on startup?

The API creates the knowledge service at startup, but it does not read all
article files then. Indexing happens through the ingest command, the admin
reindex route, or when search detects that its index must be initialized or
refreshed from published database records.

## Architecture, safety, and operations

### 47. Why use a knowledge service between the API and RAG code?

The API should handle HTTP concerns such as request validation and role
checks. The service coordinates database records with chunking and search.
That keeps SQL orchestration out of `rag/` and keeps HTTP behavior out of the
retriever.

### 48. Why does the RAG package not query tickets?

Its responsibility is to prepare and search knowledge documents. Keeping it
independent of tickets makes it reusable and prevents the retrieval library
from becoming coupled to support-domain database details.

### 49. Does a knowledge search call an LLM?

No. The implemented search uses the retriever and fake embeddings. There is
no LLM call in this Phase 5 search path.

### 50. Does the search endpoint itself send a reply to the customer?

No. It returns evidence to an authenticated caller. Reply generation,
validation, approval, and sending belong to later workflow work.

### 51. How are errors handled for malformed Markdown?

The loader raises explicit errors for missing directories, invalid front
matter, missing required values, unknown categories, duplicate slugs, and
empty article bodies. Ingestion does not pretend the operation succeeded when
source files are invalid.

### 52. What data is stored in the vector payload?

The chunk text and retrieval metadata are stored with the vector, including
article identity, title, category, heading, tags, and source. That allows a
retrieval result to be filtered and cited.

### 53. How does the feature fit the API's audit behavior?

The reindex operation is a `POST`, so it goes through the existing
non-GET audit middleware. Read-only list and search requests are not written
as state-changing audit entries by that middleware.

### 54. How was the feature tested offline?

Tests use temporary Markdown directories, in-memory SQLite, fake embeddings,
an in-memory vector store, and a FastAPI test client. They cover parsing,
chunking, indexing, search citations, API validation, role checks, missing
articles, and Qdrant behavior using a fake client.

### 55. Does the feature require Docker or cloud credentials to test?

No. The default settings support offline tests. A real Qdrant endpoint is
only needed when explicitly selecting the Qdrant backend.

### 56. Are there Docker containers or a production deployment for Phase 5?

No. Phase 5 does not create Dockerfiles, Compose wiring, cloud resources, or
deployment evidence. I would not claim those are implemented.

### 57. What would you improve before production?

I would select and validate a real embedding model, plan how to rebuild and
version its collection, monitor retrieval quality, set up Qdrant and database
network/security controls, and evaluate retrieval against representative
support questions. I would also measure latency and index refresh behavior
with production-sized content.

### 58. How would you explain the biggest design decision?

I kept article content as the durable source and treated vectors as a
replaceable index. That gives the system a simple offline default while
allowing a separate vector service later without changing the retriever's
interface.

### 59. What is one known limitation?

The default embeddings are hash-based rather than a trained semantic model.
The system demonstrates the retrieval architecture and is testable offline,
but retrieval quality must be re-evaluated with real embeddings before
production use.

### 60. How would you summarize Phase 5 in one sentence?

“Phase 5 turned support Markdown into a validated, searchable, cited
knowledge library and exposed it through role-protected APIs, with offline
defaults and a replaceable vector store.”

## Repository references

- [Phase 5 codebase explanation](../explain_codebase/phase5_explained.md)
- [Phase 5 system design evolution](../design_evolution/Phase5_Project_System_Design_Evolution.md)
- [Phase 5 infrastructure and wiring](../Infra_design_evolution/Phase5_Infra_design_evolution.md)
- [Knowledge API contract](../../docs/API_CONTRACT.md)
- [Article loader and chunker](../../rag/chunking.py)
- [Embeddings and vector stores](../../rag/embeddings.py) · [vector-store implementations](../../rag/vector_store.py)
- [Hybrid retriever](../../rag/retriever.py)
- [Knowledge API and service](../../backend/app/api/knowledge.py) · [service](../../backend/app/services/knowledge_service.py)
- [Ingest command](../../rag/ingest.py)
- [Phase 5 tests](../../tests/rag/) and [knowledge API tests](../../tests/api/test_knowledge.py)
- [Task tracker](../../TASKS.md)
