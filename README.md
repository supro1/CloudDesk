# CloudDesk

CloudDesk is an AI-assisted support workspace for support agents. It
investigates support tickets and suggests next steps while keeping people in
control of consequential actions.

## Local demo with Docker Compose

1. Copy `.env.example` to `.env` and set a non-empty local `JWT_SECRET`.
2. Run `docker compose config -q` to check the Compose configuration.
3. Run `docker compose up --build`.
4. Open `http://localhost:3000` (or `http://127.0.0.1:3000`). The browser reaches
   the API at `http://localhost:8000`.

The demo stores SQLite, Redis, and Qdrant data in Docker volumes. Redis and
Qdrant are private to the Compose network. See [deployment details](docs/DEPLOYMENT.md)
for build-time API URL configuration, Terraform scope, and delivery status.

## Local development

Run `make setup`, `make backend`, and `cd frontend && npm run dev` in separate
terminals. Set `PYTHONPATH` to include `backend` when invoking Python directly
on Windows. Run `make test` for the offline backend suite and use the frontend
commands in the Makefile comments for linting, tests, and a production build.

## Knowledge base

Run `make ingest` to load the Markdown articles from
`sample_data/knowledge_base` into the database and build the configured vector
index. Start the API with `make backend`, then use the authenticated
`/api/v1/knowledge` endpoints to browse and search the articles. An admin can
refresh the index with `POST /api/v1/knowledge/reindex`.
