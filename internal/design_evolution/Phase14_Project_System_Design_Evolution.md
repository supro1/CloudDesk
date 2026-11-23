# Phase 14 - Project System Design Evolution

## Scope and phase numbering

This document follows Phase 14 in `TASKS.md`: Evaluation and delivery
(P14-1 through P14-5). `PLAN_PHASE.md` groups evaluation and delivery as its
broader Phase 13. Phase 14 builds on the agent workflow and ticket console
from the preceding tracker phases.

## Starting point: a working application without a release gate

Before Phase 14, support staff could use the frontend and backend locally.
There were labeled tickets and tests for individual features, but no
threshold-based quality scorecard, production container images, or composed
local service topology.

```mermaid
flowchart LR
    Staff["Support staff"] --> Browser["Next.js console"]
    Browser --> API["FastAPI API"]
    API --> Existing["Existing workflow and data services"]
    Existing --> Local["Developer-managed local processes"]
    Quality["Feature tests, no aggregate release thresholds"] -.-> Existing
```

## P14-1: add a measurable quality gate

The labeled evaluation set now identifies expected ticket categories,
relevant knowledge articles where available, and whether policy requires
escalation. The scorecard runs the real offline classifier, hybrid retriever,
escalation rules, and response grounding path against those labels.

```mermaid
flowchart TB
    Dataset["13 labeled tickets"] --> Classifier["Classification accuracy"]
    Dataset --> Retriever["Expected article in top 3"]
    Dataset --> Policy["Escalation rule correctness"]
    Retriever --> Resolution["Grounded resolution output"]
    Resolution --> Citations["Citation rate"]
    Resolution --> Steps["Recommended steps in customer reply"]
    Classifier --> Thresholds["Five threshold checks"]
    Retriever --> Thresholds
    Policy --> Thresholds
    Citations --> Thresholds
    Steps --> Thresholds
    Thresholds -->|Pass| Ready["Evaluation test succeeds"]
    Thresholds -->|Below minimum| Blocked["Test fails"]
```

The thresholds are classification accuracy 0.80, retrieval hit-rate@3 0.75,
escalation correctness 0.90, citation rate 0.90, and grounding rate 0.90.
The evaluation is offline; it does not depend on a hosted model.

## P14-2: package the applications as separate images

The backend image installs locked dependencies in a build stage, then copies
only the runtime environment and the Python application into a slim runtime
image. The frontend image builds Next.js in standalone mode and copies the
standalone server and static assets into its runtime image. Both runtime
containers use a non-root account.

```mermaid
flowchart LR
    PyFiles["Backend source + uv.lock"] --> PyBuild["Python dependency build stage"]
    PyBuild --> ApiImage["Backend runtime image"]
    ApiImage --> ApiHealth["/health/live health check"]
    WebFiles["Frontend source + package lock"] --> WebBuild["Next.js standalone build"]
    WebBuild --> WebImage["Frontend runtime image"]
    WebImage --> WebHealth["/api/health health check"]
    ApiImage --> Runtime["Non-root application process"]
    WebImage --> Runtime
```

The frontend API address is a build argument because `NEXT_PUBLIC_API_URL` is
embedded in the generated browser bundle. It must name an API address
reachable by the user's browser, not a Docker-only service name.

## P14-3: describe the local services and their data flow

Compose starts Redis and Qdrant, then the backend. The backend seeds the
demo database before the one-shot knowledge-indexing service runs. The
frontend waits until the API is healthy and the article index has completed.

```mermaid
flowchart LR
    Staff["Support agent browser"] -->|localhost:3000| Frontend["Next.js frontend"]
    Staff -->|localhost:8000| Backend["FastAPI backend"]
    Frontend -->|Browser API calls via published host port| Backend
    Backend --> SQLite["SQLite + graph checkpoints volume"]
    Backend --> Redis["Redis volume"]
    Backend --> Qdrant["Qdrant volume"]
    Ingest["One-shot article indexer"] --> SQLite
    Ingest --> Qdrant
    Backend -. healthy before indexing .-> Ingest
    Ingest -. successful completion .-> Frontend
```

The Compose stack is intended for a local demonstration. The backend database
is SQLite in this configuration; Redis and Qdrant are private network
services. The API and frontend ports bind to loopback rather than every host
interface.

## P14-4: make delivery checks repeatable

GitHub Actions has separate jobs for backend checks, frontend checks,
container builds, security scans, and Terraform validation. The Terraform
roots start the cloud-specific registry and logging setup for each provider.

```mermaid
flowchart TB
    Change["Pull request or protected-branch update"] --> Tests["Backend and frontend test jobs"]
    Change --> Images["Build backend and frontend images without publishing"]
    Change --> Security["Secret, dependency, image-config, and IaC scans"]
    Change --> IaC["Terraform format and validate: AWS / Azure / GCP"]
    IaC --> AWS["ECR and CloudWatch baseline"]
    IaC --> Azure["ACR and Log Analytics baseline"]
    IaC --> GCP["Artifact Registry baseline"]
    AWS --> Human["Cloud deployment still requires design review and explicit apply"]
    Azure --> Human
    GCP --> Human
```

The cloud roots are starter configurations, not complete hosted application
stacks. They do not provision compute, ingress, application secrets,
databases, Redis, or Qdrant. CI validation does not authenticate to a cloud
account or apply resources.

## P14-5: protect deployment assumptions with tests

Static hygiene tests check that configuration stays aligned with the runtime:
container users and health checks, Compose networks and persistent storage,
environment-variable documentation, secret-file ignore rules, and expected
Terraform and CI files.

```mermaid
flowchart LR
    Hygiene["Deployment hygiene tests"] --> Docker["Image user and health checks"]
    Hygiene --> Compose["Service readiness, ports, and volumes"]
    Hygiene --> Env["Settings documented in .env.example"]
    Hygiene --> Git["No real .env tracked; state and plans ignored"]
    Hygiene --> Terraform["Provider roots and validation matrix exist"]
    Docker --> TestGate["Local pytest / CI test job"]
    Compose --> TestGate
    Env --> TestGate
    Git --> TestGate
    Terraform --> TestGate
```

## End-of-Phase-14 design

```mermaid
flowchart LR
    Agent["Support agent"] --> Browser["Browser"]
    Browser -->|Web assets| Frontend["Standalone Next.js container"]
    Browser -->|Bearer token + API requests| API["Non-root FastAPI container"]
    API --> Workflow["Existing support workflow and policy"]
    API --> DB["Persistent SQLite demo volume"]
    API --> Redis["Private Redis service"]
    API --> Vector["Private Qdrant service"]
    Indexer["One-shot knowledge indexer"] --> DB
    Indexer --> Vector
    CI["GitHub Actions"] --> Eval["Quality and hygiene gates"]
    CI --> Build["Image build checks"]
    CI --> CloudConfig["Terraform validation"]
    CloudConfig -->|starter only| Cloud["Cloud registries and logging"]
```

## Design choices and trade-offs

| Concern | Starting point | Phase 14 end state |
|---|---|---|
| Quality evidence | Individual feature tests and a labeled case list. | Five explicit evaluation metrics with minimum thresholds. |
| Runtime packaging | Developer-managed Python and Node processes. | Separate locked-dependency backend and standalone frontend images. |
| Process privileges | Local process account. | Container runtime uses non-root application accounts and health checks. |
| Local dependencies | Manually launched processes and services. | Compose coordinates backend, frontend, Redis, Qdrant, and indexing. |
| Data retention | Local paths. | Named volumes preserve SQLite/checkpoints, Redis, and Qdrant data. |
| Delivery checks | No CI workflows in this phase. | Workflow definitions validate tests, images, security, and Terraform. |
| Cloud readiness | No provider roots. | Registry/logging starter roots; application compute and service wiring remain future work. |

## Boundaries and next steps

- The Compose stack is not a production deployment template; SQLite and
  loopback ports are demo choices.
- Terraform provisions only the stated registry and logging baseline. Add
  reviewed compute, networking, ingress, secret references, and managed data
  services before a cloud deployment.
- Workflow files have been authored but are not evidence of a successful
  GitHub run.
- No cloud plan or apply has been run from this checkout.
- Docker and Terraform CLIs are not installed in the current environment;
  image and Terraform validation must run in a configured environment or CI.
- Local validation completed: 203 backend tests, Ruff, 9 frontend tests,
  frontend lint and production build, and the CD-1002 demo's rejection path.

## Related files

- [Phase 14 codebase explanation](../explain_codebase/phase14_explained.md)
- [Phase 14 infrastructure and wiring](../Infra_design_evolution/Phase14_Infra_design_evolution.md)
- [Phase 14 interview Q&A](../QnA/Phase14_Interview_QnA.md)
- [Evaluation threshold tests](../../tests/evaluation/test_thresholds.py)
- [Backend image](../../backend/Dockerfile)
- [Frontend image and standalone configuration](../../frontend/Dockerfile)
- [Compose stack](../../docker-compose.yml)
- [Terraform roots](../../deployment/)
- [Deployment documentation](../../docs/DEPLOYMENT.md)
- [GitHub Actions workflows](../../.github/workflows/)
- [Task tracker](../../TASKS.md)
