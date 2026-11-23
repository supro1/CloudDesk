# Container and cloud delivery

## Local Compose demo

Docker Compose runs the Next.js console, FastAPI service, Redis, and Qdrant.
The backend uses a SQLite file in a named volume for this demo; Redis and
Qdrant use their own named volumes. A one-shot knowledge-ingest service
indexes the sample Markdown after the backend has seeded the demo database.

1. Copy `.env.example` to `.env` and set a non-empty local `JWT_SECRET`.
2. Run `docker compose config -q` to validate interpolation and YAML.
3. Run `docker compose up --build`.
4. Open `http://localhost:3000`; the browser calls the API at
   `http://localhost:8000`.

`NEXT_PUBLIC_API_URL` is compiled into the frontend image. Set it to the
address that the user's browser can reach before building for another
environment. Do not set it to `http://backend:8000`; that name is only
resolvable inside the Compose network.

Compose binds the frontend and backend ports to loopback for local use.
Redis and Qdrant are not published to the host. This Compose configuration is
a demo stack, not a production topology.

## Terraform roots

`deployment/aws`, `deployment/azure`, and `deployment/gcp` are provider-specific
starting points for image registries and baseline logging. They are not a
complete application deployment: they do not provision the application
compute, public ingress, database, Redis, Qdrant, or external LLM. Those
services need environment-specific sizing, networking, secret references,
availability, and cost review before an apply.

Each root has a `backend.hcl.example` and a development `terraform.tfvars.example`.
Copy the relevant examples to the ignored `backend.hcl` and
`environments/dev/terraform.tfvars` files, then replace every placeholder.
Create the remote state bucket/storage container and lock mechanism before
initializing. Supply cloud authentication through the provider's short-lived
OIDC or local credential chain; do not put credentials in the variable files.

Run `make terraform-validate` (or the matching commands in
`.github/workflows/terraform-validate.yml`) before planning. No cloud apply is
performed by this repository's validation workflow.

## Delivery status

The GitHub workflows test the offline backend and frontend, build the
backend, frontend, and local Qdrant health-check images without pushing them,
scan dependencies and configuration, and validate the Terraform roots. The
workflows have not been run on GitHub and no cloud resources have been
provisioned from this checkout.

Locally, the 203-test backend suite, Ruff, 9 frontend tests, frontend lint,
the standalone frontend build, and the in-memory CD-1002 approval/rejection
demo passed. Docker and Terraform are not installed here, so their CLI
validation remains pending.
