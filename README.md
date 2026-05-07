# SwiftDeploy DevOps Automation

SwiftDeploy is a manifest-driven DevOps automation tool that deploys a containerized Flask API behind an Nginx reverse proxy using Docker Compose.

The project was completed in two stages:

- **Stage 4A:** Deployment automation, generated Docker Compose/Nginx files, stable/canary promotion, chaos testing, and teardown.
- **Stage 4B:** Observability, Open Policy Agent policy enforcement, live status monitoring, and audit reporting.

The main idea behind SwiftDeploy is simple:

> SwiftDeploy does not deploy or promote blindly. It observes the environment, asks OPA for a policy decision, explains the result, and records evidence for auditing.

---

## Project Overview

SwiftDeploy uses `manifest.yaml` as the single source of truth for deployment configuration.

Instead of manually editing deployment files, the CLI reads the manifest and generates:

```text
generated/docker-compose.yml
generated/nginx.conf
```

The deployment stack contains:

```text
Flask/Gunicorn API container
Nginx reverse proxy container
Open Policy Agent sidecar container
```

Only Nginx is exposed publicly on port `8080`. The Flask API runs internally on port `3000`, and OPA is bound to localhost on port `8181`.

---

## Architecture

### Application Traffic Flow

```text
Client / Browser / curl
        |
        v
Nginx reverse proxy
localhost:8080
        |
        v
Internal Docker network
        |
        v
Flask/Gunicorn API
internal port 3000
```

### Policy Decision Flow

```text
SwiftDeploy CLI
        |
        | collects host stats or app metrics
        v
Open Policy Agent
localhost:8181
        |
        | returns allow/deny decision with reasons
        v
SwiftDeploy CLI
        |
        | deploys, promotes, or blocks the action
        v
Docker Compose stack
```

---

## Repository Structure

```text
swiftdeploy/
├── app/
│   ├── app.py
│   └── requirements.txt
├── generated/
│   ├── docker-compose.yml
│   └── nginx.conf
├── policies/
│   ├── infrastructure.rego
│   └── canary.rego
├── templates/
│   ├── docker-compose.yml.tpl
│   └── nginx.conf.tpl
├── Dockerfile
├── README.md
├── audit_report.md
├── history.jsonl
├── manifest.yaml
└── swiftdeploy
```

---

## Technologies Used

- Python
- Flask
- Gunicorn
- Docker
- Docker Compose
- Nginx
- Open Policy Agent
- Rego
- Prometheus-style metrics
- Git and GitHub

---

# Stage 4A: Deployment Automation

Stage 4A focused on building the core deployment engine.

The tool can:

- read `manifest.yaml`;
- generate Docker Compose and Nginx files;
- deploy a Flask/Gunicorn API with Docker Compose;
- expose the app through Nginx;
- keep the application container internal;
- validate the generated deployment files;
- promote between `stable` and `canary`;
- inject controlled chaos in canary mode;
- tear down the environment cleanly.

---

## Stage 4A Commands

Generate deployment files:

```bash
./swiftdeploy init
```

Validate the environment and generated files:

```bash
./swiftdeploy validate
```

Deploy the stack:

```bash
./swiftdeploy deploy
```

Promote to canary:

```bash
./swiftdeploy promote canary
```

Promote back to stable:

```bash
./swiftdeploy promote stable
```

Tear down the environment:

```bash
./swiftdeploy teardown
```

---

## Stage 4A Features

### Manifest-Driven Deployment

SwiftDeploy uses `manifest.yaml` to control deployment behaviour.

Example values controlled by the manifest include:

```yaml
services:
  image: swift-deploy-1-node:latest
  port: 3000
  mode: stable

nginx:
  port: 8080
```

This means the manifest controls deployment configuration, while generated files are created automatically.

---

### Generated Docker Compose File

SwiftDeploy generates:

```text
generated/docker-compose.yml
```

The generated Compose file defines the application container, Nginx container, network, volumes, and later the OPA sidecar.

---

### Generated Nginx Configuration

SwiftDeploy generates:

```text
generated/nginx.conf
```

Nginx forwards requests from port `8080` to the internal Flask/Gunicorn app service.

The response header below confirms traffic is going through the generated Nginx reverse proxy:

```text
X-Deployed-By: swiftdeploy
```

---

### Stable and Canary Modes

The app supports two modes:

```text
stable
canary
```

When the app is promoted to canary, responses include:

```text
X-Mode: canary
```

---

### Chaos Testing

The `/chaos` endpoint is active only in canary mode.

Supported chaos modes:

```text
slow
error
recover
```

Slow chaos example:

```bash
curl -i -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"slow","duration":2}'
```

Recover from chaos:

```bash
curl -i -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"recover"}'
```

---

# Stage 4B: Observability, Policy Enforcement, and Auditing

Stage 4B extended SwiftDeploy with:

- Prometheus-style metrics;
- Open Policy Agent policy enforcement;
- infrastructure deployment gate;
- canary promotion gate;
- live status dashboard;
- audit history;
- Markdown audit report generation.

Stage 4B gives SwiftDeploy:

```text
Eyes   = /metrics endpoint
Brain  = OPA policy engine
Memory = history.jsonl and audit_report.md
```

---

## Observability

The Flask API exposes:

```text
/metrics
```

The metrics are in Prometheus text format.

Tracked metrics include:

```text
http_requests_total
http_request_duration_seconds
app_uptime_seconds
app_mode
chaos_active
```

State values:

```text
app_mode 0      = stable
app_mode 1      = canary
chaos_active 0  = no chaos
chaos_active 1  = slow chaos
chaos_active 2  = error chaos
```

Test metrics:

```bash
curl -s http://localhost:8080/metrics
```

Useful filtered output:

```bash
curl -s http://localhost:8080/metrics | grep -E "http_requests_total|app_uptime_seconds|app_mode|chaos_active"
```

---

## Open Policy Agent

OPA runs as a sidecar container.

It is reachable by the CLI at:

```text
http://localhost:8181
```

OPA is deliberately not exposed through Nginx.

OPA loads Rego files from:

```text
policies/
```

The CLI does not make allow/deny decisions by itself. It collects facts and sends them to OPA. OPA returns a structured decision.

Example decision:

```json
{
  "allow": false,
  "domain": "infrastructure",
  "reason": "Infrastructure policy blocked this action.",
  "violations": [
    "Disk free is below the required limit."
  ]
}
```

---

## Policy Domains

SwiftDeploy uses separate policy domains.

### 1. Infrastructure Policy

File:

```text
policies/infrastructure.rego
```

Question answered:

```text
Is the host safe enough for deployment?
```

It blocks deployment if:

```text
Disk free < 10GB
CPU load > 2.0
```

The thresholds are stored in `manifest.yaml`, not hardcoded directly in Rego.

---

### 2. Canary Safety Policy

File:

```text
policies/canary.rego
```

Question answered:

```text
Is the canary healthy enough to promote?
```

It blocks promotion if:

```text
Error rate > 1%
P99 latency > 500ms
```

Before promotion, SwiftDeploy scrapes `/metrics`, calculates the error rate and P99 latency, sends the values to OPA, and only promotes if OPA allows the action.

---

## OPA Isolation Test

OPA must not be accessible through Nginx.

Test through Nginx:

```bash
curl -i http://localhost:8080/v1/data/swiftdeploy/infrastructure/decision
```

Expected result:

```text
404 Not Found
```

Test OPA directly:

```bash
curl -i http://localhost:8181/health
```

Expected result:

```text
HTTP/1.1 200 OK
{}
```

This proves OPA is available to the CLI but not exposed through the public Nginx ingress.

---

## Hard Gate Deployment Test

To prove that deployment can be blocked, the infrastructure threshold can be temporarily raised in `manifest.yaml`.

Example:

```yaml
policy:
  infrastructure:
    min_disk_free_gb: 9999
```

Then run:

```bash
./swiftdeploy deploy
```

Expected result:

```text
[POLICY BLOCK] deploy was blocked by infrastructure policy
```

After the test, restore the threshold:

```yaml
min_disk_free_gb: 10
```

This proves that `swiftdeploy deploy` is policy-gated.

---

## Canary Safety Test

Promote to canary:

```bash
./swiftdeploy promote canary
```

Inject slow chaos:

```bash
curl -i -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"slow","duration":2}'
```

Generate traffic:

```bash
for i in {1..20}; do
  curl -s http://localhost:8080/ > /dev/null
  echo "slow request $i"
  sleep 1
done
```

Attempt promotion:

```bash
./swiftdeploy promote stable
```

Expected result:

```text
[POLICY BLOCK] promote stable was blocked by canary policy
```

Recover from chaos:

```bash
curl -i -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"recover"}'
```

This proves that unhealthy canaries are not promoted blindly.

---

## Status Dashboard

Run once:

```bash
./swiftdeploy status --once
```

Run continuously:

```bash
./swiftdeploy status
```

The status dashboard displays:

```text
current mode
chaos state
requests per second
window requests
window errors
error rate
P99 latency
infrastructure policy status
canary policy status
```

Every status scrape is appended to:

```text
history.jsonl
```

---

## Audit Report

Generate the audit report:

```bash
./swiftdeploy audit
```

This creates:

```text
audit_report.md
```

The report includes:

```text
summary
timeline
mode changes
chaos state changes
policy violations
```

This provides an audit trail for the deployment workflow.

---

# Quick Demo Commands

Use these commands to demonstrate the project quickly:

```bash
./swiftdeploy validate
./swiftdeploy deploy
curl -i http://localhost:8080/healthz
curl -i http://localhost:8080/
curl -s http://localhost:8080/metrics | grep -E "http_requests_total|app_uptime_seconds|app_mode|chaos_active"
curl -i http://localhost:8181/health
curl -i http://localhost:8080/v1/data/swiftdeploy/infrastructure/decision
./swiftdeploy promote canary
curl -i http://localhost:8080/ | grep -E "HTTP|X-Mode|X-Deployed-By"
./swiftdeploy status --once
./swiftdeploy audit
head -40 audit_report.md
```

---

# 5-Minute Defence Summary

SwiftDeploy is a manifest-driven DevOps automation tool that deploys a Flask/Gunicorn API behind Nginx using Docker Compose.

In Stage 4A, I built the deployment engine. It reads `manifest.yaml`, generates Docker Compose and Nginx files, validates the environment, deploys the stack, supports stable/canary promotion, supports chaos testing, and can tear down the environment.

In Stage 4B, I added observability, OPA policy enforcement, and auditing. The app exposes `/metrics`, the CLI scrapes those metrics, OPA makes policy decisions, and the tool blocks unsafe deploys or promotions. The `status` command shows live health and policy compliance, while the `audit` command generates a Markdown audit report.

The key design principle is that SwiftDeploy does not deploy or promote blindly. It observes, asks OPA, explains the result, and records evidence.

---

## Security Decisions

SwiftDeploy includes the following security choices:

```text
app service is internal-only
Nginx is the only public application entry point
OPA is bound to localhost only
containers drop Linux capabilities
containers use no-new-privileges
the app runs as a non-root user
```

These choices reduce unnecessary exposure and make the deployment safer.

---

## Troubleshooting

### Docker Engine is not reachable

Open Docker Desktop and confirm:

```bash
docker version
```

### Script does not run with `./swiftdeploy`

Use:

```bash
python swiftdeploy --help
```

or:

```bash
python swiftdeploy validate
```

### Port 8080 is already in use

Run:

```bash
./swiftdeploy teardown
```

Then deploy again.

### OPA is unavailable

Check:

```bash
curl -i http://localhost:8181/health
```

If it fails, redeploy:

```bash
./swiftdeploy deploy
```

---

## Lessons Learned

This project taught me that DevOps is not only about running containers.

A good deployment workflow should be:

```text
repeatable
observable
policy-driven
secure
auditable
```

The biggest lesson is:

> Deploying is easy. Deploying safely is the real DevOps challenge.

---

## Possible Improvements

Future improvements could include:

```text
Prometheus server integration
Grafana dashboard
GitHub Actions pipeline
OPA unit tests
structured JSON logs
automatic rollback
Slack notifications
cloud deployment
```

---

## Conclusion

SwiftDeploy demonstrates deployment automation, reverse proxying, container security, observability, policy-as-code, canary safety, chaos testing, and audit reporting in one workflow.

The final project does not only ask:

```text
Can I deploy?
```

It also asks:

```text
Is it safe to deploy?
```
