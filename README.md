# CloudDesk

## Knowledge base

Run `make ingest` to load the Markdown articles from
`sample_data/knowledge_base` into the database and build the configured vector
index. Start the API with `make backend`, then use the authenticated
`/api/v1/knowledge` endpoints to browse and search the articles. An admin can
refresh the index with `POST /api/v1/knowledge/reindex`.
