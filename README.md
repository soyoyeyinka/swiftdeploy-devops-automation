# SwiftDeploy

SwiftDeploy is a manifest-driven DevOps automation tool that deploys a containerized Python API behind an Nginx reverse proxy using Docker Compose.

The project started as a deployment automation tool and was extended in Stage 4B with observability, policy enforcement, and auditing.

SwiftDeploy now provides:

- Manifest-driven deployment
- Automatic Docker Compose and Nginx configuration generation
- Dockerized Flask API served with Gunicorn
- Nginx reverse proxy
- Prometheus-style metrics
- Open Policy Agent policy enforcement
- Stable and canary deployment modes
- Controlled chaos testing
- Live status dashboard
- Audit history and Markdown audit report generation

---

## Project Overview

SwiftDeploy uses `manifest.yaml` as the single source of truth for deployment configuration.

Instead of manually editing deployment files, the CLI reads the manifest and generates:

- `generated/docker-compose.yml`
- `generated/nginx.conf`

The deployment stack contains:

- A Flask/Gunicorn application container
- An Nginx reverse proxy container
- An Open Policy Agent sidecar container

The application container is not exposed directly to the host. Only Nginx is exposed publicly on port `8080`. OPA is reachable by the CLI on localhost port `8181`, but it is not exposed through the Nginx ingress.

---

## Architecture

Request flow:

Client or curl request -> Nginx reverse proxy on port 8080 -> internal Docker network -> Flask/Gunicorn API on port 3000

Policy flow:

SwiftDeploy CLI -> collects host stats or application metrics -> sends facts to OPA -> OPA returns structured decision -> CLI allows or blocks the action

OPA is intentionally isolated from public traffic. It is not routed through Nginx.

---

## Folder Structure

swiftdeploy/
- app/
  - app.py
  - requirements.txt
- generated/
  - docker-compose.yml
  - nginx.conf
- policies/
  - infrastructure.rego
  - canary.rego
- templates/
  - docker-compose.yml.tpl
  - nginx.conf.tpl
- Dockerfile
- README.md
- BLOG_POST.md
- manifest.yaml
- swiftdeploy
- history.jsonl
- audit_report.md

---

## Main Technologies Used

- Python
- Flask
- Gunicorn
- Docker
- Docker Compose
- Nginx
- Open Policy Agent
- Rego policy language
- Prometheus text-format metrics
- Git and GitHub

---

## Manifest-Driven Deployment

The `manifest.yaml` file controls the deployment.

It includes:

- project details
- service name
- Docker image name
- application port
- deployment mode
- application version
- Nginx image and port
- network settings
- log volume settings
- OPA URL
- infrastructure policy thresholds
- canary safety thresholds

The deployment mode is controlled through:

`services.mode`

Supported modes:

- `stable`
- `canary`

The key design decision is that deployment behaviour is controlled by configuration, not by manually editing Docker Compose files.

---

## Application Endpoints

### Root Endpoint

`GET /`

Returns the application message, current mode, version, and timestamp.

Example response contains:

- `message`
- `mode`
- `version`
- `timestamp`

---

### Health Check Endpoint

`GET /healthz`

Returns application health information.

Example response contains:

- `status`
- `mode`
- `version`
- `uptime_seconds`

---

### Metrics Endpoint

`GET /metrics`

Exposes Prometheus-compatible metrics.

Tracked metrics include:

- `http_requests_total`
- `http_request_duration_seconds`
- `app_uptime_seconds`
- `app_mode`
- `chaos_active`

State values:

- `app_mode 0` means stable
- `app_mode 1` means canary
- `chaos_active 0` means no chaos
- `chaos_active 1` means slow chaos
- `chaos_active 2` means error chaos

---

### Chaos Endpoint

`POST /chaos`

The chaos endpoint only works in canary mode.

Supported chaos modes:

- `slow`
- `error`
- `recover`

Slow chaos example:

`curl -i -X POST http://localhost:8080/chaos -H "Content-Type: application/json" -d '{"mode":"slow","duration":2}'`

Error chaos example:

`curl -i -X POST http://localhost:8080/chaos -H "Content-Type: application/json" -d '{"mode":"error","rate":0.5}'`

Recover from chaos:

`curl -i -X POST http://localhost:8080/chaos -H "Content-Type: application/json" -d '{"mode":"recover"}'`

---

## CLI Commands

SwiftDeploy is controlled using the `swiftdeploy` CLI.

Available commands:

- `./swiftdeploy init`
- `./swiftdeploy validate`
- `./swiftdeploy deploy`
- `./swiftdeploy promote stable`
- `./swiftdeploy promote canary`
- `./swiftdeploy status`
- `./swiftdeploy status --once`
- `./swiftdeploy audit`
- `./swiftdeploy teardown`

On Windows Git Bash, the script can also be run with Python:

`python swiftdeploy <command>`

---

## Build the Docker Image

Before deployment, build the application image:

`docker build -t swift-deploy-1-node:latest .`

Confirm the image exists:

`docker images | grep swift-deploy-1-node`

---

## Generate Deployment Files

Run:

`./swiftdeploy init`

This generates:

- `generated/docker-compose.yml`
- `generated/nginx.conf`

The files are generated from templates using values in `manifest.yaml`.

---

## Validate the Deployment

Run:

`./swiftdeploy validate`

Validation checks include:

- `manifest.yaml` exists
- required manifest keys are present
- Docker Compose and Nginx templates exist
- generated files exist
- Docker Engine is reachable
- Docker Compose is available
- application image exists locally
- generated Docker Compose file is valid
- Nginx includes the `X-Deployed-By: swiftdeploy` header
- app service is internal-only
- OPA sidecar exists
- OPA is bound to localhost only
- containers use security hardening
- Nginx port is available or already used by this stack

---

## Deploy the Stack

Run:

`./swiftdeploy deploy`

The deploy command:

1. Regenerates deployment files from the manifest.
2. Starts the OPA sidecar.
3. Sends host facts to OPA for the pre-deploy infrastructure policy check.
4. Blocks deployment if OPA denies the action.
5. Runs validation checks.
6. Starts the full Docker Compose stack.
7. Waits for the application health check to pass.

The application becomes available at:

`http://localhost:8080`

---

## OPA Policy Enforcement

SwiftDeploy uses Open Policy Agent as the policy decision engine.

The CLI does not make allow or deny decisions by itself. It only collects facts and sends them to OPA.

OPA returns structured decisions containing:

- `allow`
- `domain`
- `reason`
- `violations`

This ensures every blocked deployment or promotion includes a human-readable reason.

---

## Policy Domains

The project has two separate Rego policy domains.

### Infrastructure Policy

File:

`policies/infrastructure.rego`

Question owned by this policy:

Is the host safe enough for deployment?

It blocks deployment if:

- disk free space is below 10GB
- CPU load is above 2.0

The thresholds are stored in `manifest.yaml`, not hardcoded in the Rego file.

---

### Canary Safety Policy

File:

`policies/canary.rego`

Question owned by this policy:

Is the canary healthy enough to promote?

It blocks promotion if:

- error rate is above 1%
- P99 latency is above 500ms over the evaluation window

The CLI scrapes `/metrics`, calculates error rate and P99 latency, sends those values to OPA, and waits for OPA's decision.

---

## Stable and Canary Promotion

Promote to canary:

`./swiftdeploy promote canary`

Confirm canary mode:

`curl -i http://localhost:8080/`

Expected canary signal:

`X-Mode: canary`

Promote back to stable:

`./swiftdeploy promote stable`

In stable mode, the `X-Mode: canary` header should no longer appear.

---

## Chaos Testing

Chaos testing is used to prove that the canary safety policy works.

To inject slow chaos:

`curl -i -X POST http://localhost:8080/chaos -H "Content-Type: application/json" -d '{"mode":"slow","duration":2}'`

Generate traffic:

`for i in {1..20}; do curl -s http://localhost:8080/ > /dev/null; echo "slow request $i"; sleep 1; done`

Attempt promotion while canary is unhealthy:

`./swiftdeploy promote stable`

Expected result:

The canary policy should block promotion if P99 latency is above the allowed threshold.

Recover from chaos:

`curl -i -X POST http://localhost:8080/chaos -H "Content-Type: application/json" -d '{"mode":"recover"}'`

---

## Status Dashboard

Run:

`./swiftdeploy status`

Run once:

`./swiftdeploy status --once`

The status command shows:

- current app mode
- current chaos state
- request rate
- error rate
- P99 latency
- infrastructure policy compliance
- canary policy compliance

Every status scrape is appended to:

`history.jsonl`

This file acts as the audit trail.

---

## Audit Report

Generate the audit report:

`./swiftdeploy audit`

This creates:

`audit_report.md`

The audit report includes:

- summary of samples analysed
- timeline of mode changes
- timeline of chaos state changes
- policy violations

The report is formatted as GitHub Flavored Markdown.

---

## OPA Isolation Test

OPA must not be accessible through Nginx.

Test Nginx path:

`curl -i http://localhost:8080/v1/data/swiftdeploy/infrastructure/decision`

Expected result:

A normal application or Nginx response such as 404, not an OPA policy response.

Test OPA directly:

`curl -i http://localhost:8181/health`

Expected result:

OPA health response.

This proves OPA is reachable by the CLI but isolated from public ingress.

---

## Security Notes

SwiftDeploy includes the following security practices:

- app container is not publicly exposed
- Nginx is the only public application entry point
- OPA is bound to localhost only
- containers drop Linux capabilities
- containers use `no-new-privileges:true`
- app runs inside an internal Docker network
- Nginx adds the `X-Deployed-By: swiftdeploy` response header

---

## Troubleshooting

### Docker Engine is not reachable

Open Docker Desktop and wait until Docker Engine is running.

Then run:

`docker version`

### Docker Compose is unavailable

Check:

`docker compose version`

### Port 8080 is already in use

Run:

`./swiftdeploy teardown`

Or change the Nginx port in `manifest.yaml`.

### OPA is unavailable

Check:

`curl -i http://localhost:8181/health`

If OPA is not running, redeploy:

`./swiftdeploy deploy`

### CLI does not run with `./swiftdeploy`

Use:

`python swiftdeploy <command>`

Example:

`python swiftdeploy validate`

---

## Defence Summary

SwiftDeploy demonstrates a practical DevOps workflow that combines deployment automation, observability, policy-as-code, and auditing.

The project shows how to:

- use a manifest as the source of truth
- generate infrastructure files from templates
- deploy containers with Docker Compose
- route traffic through Nginx
- keep the application service private
- expose Prometheus-style metrics
- use OPA for deployment and promotion decisions
- block unsafe actions with clear policy reasons
- promote between stable and canary modes
- inject controlled chaos
- monitor service health and policy compliance
- produce an audit report from operational history

The most important design principle is that SwiftDeploy does not deploy or promote blindly. It observes the environment, asks OPA for a policy decision, surfaces the reason to the operator, and records activity for audit purposes.
