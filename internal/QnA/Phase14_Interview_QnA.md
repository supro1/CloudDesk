# Phase 14 - Evaluation and Delivery: Interview Questions and Answers

These questions follow Phase 14 in `TASKS.md`: P14-1 through P14-5. The
answers are written to be spoken aloud and distinguish local validation from
cloud deployment.

## Goals and system design

### 1. What was the goal of Phase 14?

To measure support quality, package the application consistently, describe
how its local services connect, and add repeatable delivery checks.

### 2. How would you explain this phase to a non-technical interviewer?

I added a quality scorecard, packed the web screen and API so they can be
moved consistently, and connected the demo services. I also prepared
automated checks and cloud starting points, without claiming that cloud
resources were deployed.

### 3. What did the application have before this phase?

It had a support-agent console, API, workflow, and feature tests. It did not
yet have threshold-based evaluation, application images, a Compose demo
stack, or delivery workflows.

### 4. What do the five Phase 14 tasks cover?

P14-1 adds evaluation thresholds. P14-2 adds backend and frontend images.
P14-3 wires the local Compose stack. P14-4 adds cloud and CI scaffolds.
P14-5 tests deployment hygiene.

### 5. Does this phase change how a support ticket is handled?

No new ticket workflow behavior is intended. It adds ways to measure,
package, and validate the existing behavior.

## Evaluation and quality thresholds

### 6. Why add evaluation thresholds if there are already unit tests?

Unit tests check particular behaviors. Evaluation thresholds check whether
the system performs well enough across a representative labeled set of
support cases.

### 7. Which quality measures are checked?

Ticket classification, finding an expected article in the top three
results, policy escalation correctness, citations in replies, and inclusion
of recommended steps in replies.

### 8. What are the required minimum scores?

Classification accuracy is at least 0.80, retrieval hit-rate@3 at least
0.75, escalation correctness at least 0.90, citation rate at least 0.90,
and grounding rate at least 0.90.

### 9. What does hit-rate@3 mean?

For each labeled case with an expected article, it checks whether that
article appears anywhere in the first three search results.

### 10. What is grounding in this evaluation?

It checks whether each recommended troubleshooting step is present in the
customer-facing reply, rather than allowing a reply to omit the actual
recommended actions.

### 11. How is citation rate measured?

For cases with evidence, the test checks that the generated reply contains
the article title, link, and source reference for every retrieved item.

### 12. Why are expected outcomes added to the evaluation data?

The test needs a known answer to compare with the system result. The dataset
now records expected categories, expected knowledge articles where the
sample library has a suitable article, and expected escalation decisions.

### 13. Why are some expected articles empty?

The knowledge library does not contain a suitable article for every case,
such as the missing-files and prompt-injection examples. Those cases still
participate in classification and escalation evaluation, but not article
hit-rate calculations.

### 14. Does the evaluation use a real AI API?

No. It runs offline with the deterministic fake provider and local sample
articles, so tests do not need an API key or external network access.

### 15. What happens when a threshold is missed?

The pytest job fails. In CI, a failing required check prevents the pull
request from being treated as passing.

## Docker images and health checks

### 16. What is a Docker image?

It is a packaged application and its runtime requirements. It helps the
same software start in a more consistent way on different machines.

### 17. Why are there two images?

The backend is a Python API and the frontend is a Next.js web application.
They have different runtimes and can be built and started independently.

### 18. Why is the backend image multi-stage?

The first stage installs locked Python dependencies. The runtime stage
copies the virtual environment and application code without keeping the
dependency-building tools.

### 19. What is Next.js standalone output?

It is a production package containing the Next.js server and the files it
needs, so the runtime image does not need the full development toolchain.

### 20. Why run containers as non-root?

If a process is compromised, a non-root user has fewer permissions inside
the container than an administrator account.

### 21. What do the health checks do?

The backend checks `/health/live`; the frontend checks `/api/health`.
They let Docker and Compose tell whether each process is responding.

### 22. Why does the frontend API address use a build argument?

`NEXT_PUBLIC_API_URL` is embedded into the browser's JavaScript during the
Next.js build. It must point to an address the user's browser can reach.

### 23. Why not set the browser API address to `http://backend:8000`?

That name is Docker's internal service name. The browser runs on the user's
computer and cannot resolve that private container name; the local demo
uses `http://localhost:8000`.

### 24. What do `.dockerignore` files protect?

They keep local databases, secrets, caches, installed dependencies, and
unrelated files out of the Docker build context.

## Compose, networking, and persistence

### 25. Which services does the Compose demo run?

The frontend, backend, Redis, Qdrant, and a one-time knowledge-indexing
service.

### 26. What is the `edge` network for?

It connects the frontend and backend containers. The browser calls the API
through the host-published API port.

### 27. What is the `data` network for?

It connects the backend and one-time indexer to Redis and Qdrant. Redis and
Qdrant are not published as host ports.

### 28. Why are there named volumes?

Named volumes keep the SQLite/checkpoint database, Redis data, and Qdrant
data when containers are recreated.

### 29. Why does the indexer run after the backend?

The backend first seeds the demo database. Indexing then adds article
records and Qdrant vectors. If indexing ran first, article records could
make the application's database seeding logic think the database was
already initialized.

### 30. Why does the frontend wait for the indexer?

It avoids presenting the demo as ready before the knowledge articles have
been indexed for search.

### 31. Is SQLite appropriate for a production multi-instance deployment?

Not usually. SQLite is used here to keep the local demo self-contained.
Production would use a managed database selected and reviewed for the
chosen cloud environment.

### 32. Are the demo ports exposed to the whole network?

No. The frontend and backend ports bind to `127.0.0.1` for local use.
Redis and Qdrant have no host port mapping.

## Terraform, CI, and delivery status

### 33. What is Terraform used for here?

Terraform describes cloud resources as configuration that can be reviewed
and validated before someone applies it.

### 34. Which cloud providers have starting roots?

AWS, Azure, and Google Cloud. The current roots create container registries
and basic logging resources.

### 35. Are these roots a complete CloudDesk deployment?

No. They do not create application compute, public ingress, application
secrets, databases, Redis, or Qdrant. Those components still need
environment-specific design and implementation.

### 36. Why not include real credentials in Terraform files?

Credentials should be supplied through an approved cloud identity or
environment mechanism, not committed to source control. The example files
contain placeholders only.

### 37. What does Terraform CI validate?

It checks formatting, initializes each root without a cloud backend, and
runs `terraform validate` for AWS, Azure, and Google Cloud.

### 38. What do the GitHub workflows check?

The definitions cover offline backend tests and linting, frontend lint,
tests and build, Docker image builds, security scans, and Terraform
validation.

### 39. Have those workflows passed on GitHub?

They have been added but have not been run on GitHub in this checkout.
I report that as unverified rather than claiming a CI pass.

### 40. Have cloud resources been deployed?

No. No cloud credentials were used, and no Terraform apply was run.

### 41. Why does `.gitignore` include Terraform plan patterns?

Plans can contain sensitive configuration and are generated locally. The
ignore rules keep them, state files, backend configuration, and actual
variable files out of commits.

### 42. What do the deployment hygiene tests check?

They check non-root container configuration, health checks, Compose
dependencies and storage, documented backend settings, ignored secrets and
state, and the provider validation matrix.

### 43. What could be improved before production?

Complete and review the cloud compute, networking, ingress, secret,
database, Redis, and Qdrant design; run image and Terraform validation in
CI; then run a reviewed plan and a separately approved deployment.

### 44. How would you summarize Phase 14 in one sentence?

"Phase 14 adds measurable quality gates and repeatable packaging, while
keeping local validation, cloud setup, and actual deployment clearly
separate."

## Repository references

- [Phase 14 codebase explanation](../explain_codebase/phase14_explained.md)
- [Phase 14 system design evolution](../design_evolution/Phase14_Project_System_Design_Evolution.md)
- [Phase 14 infrastructure and wiring](../Infra_design_evolution/Phase14_Infra_design_evolution.md)
- [Evaluation threshold tests](../../tests/evaluation/test_thresholds.py)
- [Deployment hygiene tests](../../tests/deployment/test_hygiene.py)
- [Compose stack](../../docker-compose.yml)
- [Deployment guide](../../docs/DEPLOYMENT.md)
- [Terraform roots](../../deployment/)
- [GitHub Actions workflows](../../.github/workflows/)
- [Task tracker](../../TASKS.md)
