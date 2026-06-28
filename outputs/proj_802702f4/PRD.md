# PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 1. Goal Description

### 1.1. Core Mission & Vision
The mission of this project is to deliver a highly collaborative, enterprise-ready, and sub-100ms p95 latency Task Management Platform (Project ID: `proj_802702f4`). The application is designed to support high-velocity, concurrent team workflows (e.g., real-time Kanban transitions, instant notification broadcasts, and secure multi-tenant workspace collaboration) while maintaining a resilient, zero-trust security footprint and a strictly reconciled infrastructure cost of **$2,476.00/month**.

### 1.2. Strategic Objectives
*   **Performance:** Achieve and sustain sub-100ms p95 API response times and sub-millisecond local authorization lookups.
*   **Scalability:** Effortlessly support $100,000+$ concurrent WebSocket connections and horizontal application scaling without database write or thread exhaustion.
*   **Security:** Enforce strict, cryptographically validated multi-tenant workspace isolation at both the application and database tiers, completely eliminating Broken Object Level Authorization (BOLA/IDOR) risks.
*   **Operational Resilience:** Guarantee a zero-data-loss event pipeline through a transactional outbox model, fail-open rate limiting, and database-native high-availability failovers.

---

## 2. Target Persona & Use Cases

### 2.1. Target Personas

#### Persona A: Enterprise Team Lead (Alex, Engineering Director)
*   **Needs:** High-velocity project overview, real-time board updates, strict workspace boundaries to protect IP between client projects, zero lag during interactive planning sessions.
*   **Pain Points:** Stale board views, data leakage between team workspaces, and system downtime during database schema updates.

#### Persona B: Collaborative Developer (Devon, Software Engineer)
*   **Needs:** Bidirectional task updates, seamless offline-to-online transitions, markdown documentation support inside tasks, and rapid task linking.
*   **Pain Points:** HTML injection vulnerabilities from rich text, lost comments during connection blips, and sluggish interface feedback.

#### Persona C: Platform Administrator (Sam, Site Reliability Engineer)
*   **Needs:** Full observability across distributed transactions, cost-efficient resource provisioning, fast container boot times, and automated secret rotation.
*   **Pain Points:** Fragmented distributed traces, out-of-memory (OOM) pod crashes, high NAT Gateway data transit fees, and stateful volume mounting bottlenecks.

### 2.2. Core Use Cases

```
    +-------------------------------------------------------------------+
    |                          Core Use Cases                           |
    +-------------------------------------------------------------------+
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
+──────────────────+     +──────────────────+     +──────────────────+
│    Use Case 1    │     │    Use Case 2    │     │    Use Case 3    │
│ Real-Time Kanban │     │ Secure Tenant    │     │ Zero-Downtime    │
│ Drag-and-Drop    │     │ Switch (RLS)     │     │ Schema Upgrade   │
+──────────────────+     +──────────────────+     +──────────────────+
```

#### Use Case 1: Real-Time Kanban Drag-and-Drop Collaboration
*   **Flow:** Devon drags a task card from "In Progress" to "Completed" on a shared Kanban board.
*   **System Action:** The frontend dispatches a gRPC mutation to the Go Command Service. The update is committed to AWS Aurora PostgreSQL, generating an outbox event. The Outbox Recovery Worker publishes the event to Redpanda. The Elixir Real-time Sync Service consumes the event and instantly broadcasts a lightweight JSON delta frame over WebSockets to all other active workspace users.
*   **UX Experience:** Other team members see the card transition in real-time within < 100ms.

#### Use Case 2: Secure Tenant Switching with Row-Level Security (RLS)
*   **Flow:** Alex switches from the "Client A" workspace to the "Client B" workspace.
*   **System Action:** The Query Service extracts Alex's asymmetric RS256 JWT claims, dynamically verifies his workspace membership against the secure context claims in Go, and initiates a read query on AWS Aurora PostgreSQL. The driver injects his `workspace_id` into the transaction context using `SET LOCAL app.current_workspace_id`. The database engine executes Row-Level Security (RLS) filters on the query.
*   **UX Experience:** Alex is blocked from accessing any Client A tasks while in the Client B workspace context.

#### Use Case 3: Zero-Downtime Schema Upgrade
*   **Flow:** SRE Sam deploys a database migration to introduce a new required database attribute.
*   **System Action:** The CI/CD pipeline triggers an isolated Kubernetes `Job` via Helm pre-upgrade hooks. The migration executes an "Expand-and-Contract" strategy, adding the column safely while existing pods continue writing to legacy columns. New application pods are rolled out via ArgoCD, safely reading/writing from the new column before the old column is deprecated.
*   **UX Experience:** Zero system downtime or transactional lockups.

---

## 3. Functional Requirements

### 3.1. Workspace & Task Lifecycle Management
*   **Multi-Tenant Workspaces:** Users can create, join, and switch between isolated workspaces. All core tables (tasks, comments, projects) must be partitioned logically via declarative hash partitioning on `workspace_id`.
*   **Task CRUD Operations:** Standard task properties include Title, Description (Markdown), Status, Priority, Assignee, and Custom Fields.
*   **Asymmetric Soft-Deletes:** Physical hard-deletes are structurally banned in standard transactional pathways. When a task is deleted, the system sets `is_deleted = TRUE` and updates the `last_modified` timestamp.
*   **Database Tombstone Tracking:** For administrative fallback scenarios where raw physical deletions occur, a native database trigger must intercept and log the deleted record metadata (`table_name`, `record_id`, `workspace_id`) to a `deleted_tombstones` table to ensure delete synchronization with downstream search and caching layers.

### 3.2. Real-Time Synchronization Engine
*   **Stateful WebSockets:** Bidirectional communication channels are hosted on the Elixir Real-time Sync Service using Phoenix Channels.
*   **Background-Tab Resource Protection:** To prevent browser background-tab throttling from causing thundering-herd reconnection storms, the Elixir WebSocket service enforces a **5-minute passive validation phase** for throttled client states. During this phase, all outgoing real-time payload pushes are completely blocked, and only `"token_required"` control frames are transmitted.
*   **Client Jittered Backoff:** Reconnecting clients must implement randomized exponential backoff:
    $$t = \text{Min}\left(60, 2^{\text{attempt}}\right) \pm \text{Random}(0.5 \times t)$$

### 3.3. Authentication, Authorization & Session Security
*   **Asymmetric JWT Verification:** User identity is verified via OIDC asymmetric JWTs (signed with RS256). Token payloads must remain stateless, containing only Identity Metadata (User ID, Session ID, Global Role) and **no** dynamic, fast-changing lists of authorized `workspace_ids`.
*   **Dynamic JWKS Key Resolution:** Public keys must be dynamically retrieved from the Go Auth Service's JWKS endpoint (`/.well-known/jwks.json`) and cached locally in Elixir using `Cachex` with a **24-hour Time-to-Live (TTL)**.
*   **Dynamic Session Revocation:** All active user permissions are stored as a Redis Hash (`user_acl:<user_id>`). When an administrator revokes a user's workspace permissions, the Command Service performs a synchronous update to the Redis ACL store and immediately publishes a `user_revoked` message to a persistent **Redis Stream**.

---

## 4. Non-Functional Constraints

### 4.1. Performance & Latency Budgets
*   **p95 Response Times:** All write mutations and read queries must resolve in **sub-100ms** at the API gateway edge.
*   **Authorization Latency:** Workspace access checks must resolve in **sub-milliseconds** via the local Redis ACL cache.
*   **Query Coalescing:** Fallback read paths to the database during Redis outages must leverage Go `singleflight` to merge concurrent read requests for identical cache keys into a single database operation.

### 4.2. Scalability Metrics
*   **Concurrent Connections:** The Real-time Sync Service must sustain **$100,000+$** active WebSocket connections simultaneously.
*   **Database Capacity Scaling:** AWS Aurora Serverless v2 is configured to scale dynamically between **0.5 and 8 ACUs** (Aurora Capacity Units) per AZ. AWS Budgets must trigger automated SRE alerts if average ACU utilization exceeds **4.0 ACUs** over a rolling 4-hour window.

### 4.3. Security & Zero-Trust Architecture
*   **Linkerd Service Mesh:** Enforce mutual TLS (mTLS) for all service-to-service communication with automatic cryptographic certificate rotation. Pods within the `platform` namespace are configured with `failurePolicy: Fail` on mutating webhooks to block any unencrypted pod deployments.
*   **PgBouncer Session Context Isolation:** In PgBouncer's Transaction Mode, physical connections are multiplexed at transaction boundaries. To prevent `app.current_workspace_id` from leaking across tenant boundaries on reused physical connections, the Go database client must execute `SET LOCAL` inside an explicit transaction block wrapped in a deferred rollback block:

```go
defer func() {
    _ = tx.Rollback(ctx) // Safe rollback guarantees PgBouncer connection cleanup
}()
```

*   **JWKS-DDoS Mitigation:** To prevent an attacker from flooding the WebSocket gateway with invalid Key IDs (`kid`) to block legitimate key rotations, the Elixir JWKS resolver must decouple network fetching from the client request-response path using `Task.Supervisor`. The negative cache must be bounded to **10,000 entries** to prevent out-of-memory (OOM) exploitation.

### 4.4. Reliability & High Availability (HA)
*   **Active-Active Outbox Recovery Worker:** The Outbox Recovery Worker must scale to `replicas: 2` using the `RollingUpdate` deployment strategy. It must leverage PostgreSQL's native transaction locking mechanism (`FOR UPDATE SKIP LOCKED`) to process outbox records in parallel without lock contention or duplicate event delivery.
*   **Outbox Event Reclaim Threshold:** If a worker pod crashes or experiences network partitions, events stalled in the `processing` state for longer than **30 seconds** must be automatically reclaimed and re-processed during subsequent sweeps.
*   **Safe Redis Consumer Reaper:** The active Lua cleanup script must query `XINFO CONSUMERS` to verify active client connections and verify that the Pending Entries List (PEL) is empty (`pending_count == 0`) before destroying a consumer group. Elixir nodes must explicitly trap exits (`Process.flag(:trap_exit, true)`) to guarantee the execution of `XGROUP DESTROY` on pod shutdown.

### 4.5. Maintainability & Code Quality
*   **Multi-Stage Container Builds:** Go command/query services must compile to static, optimized binaries with stripped symbols and run inside ultra-minimal distroless execution environments (`gcr.io/distroless/static-debian12`). Elixir services must compile inside a robust builder stage (with `build-base` and `openssl-dev`) and run within a matching Erlang/OTP Alpine runtime.
*   **Goldmark & Bluemonday Integration:** Custom, fragile regular-expression-based markdown sanitization is banned. Raw markdown must be preserved as the database source of truth. Markdown compilation to HTML is performed using `goldmark`, and dynamic HTML sanitization is executed on the read-path using `bluemonday`’s `UGCPolicy()` to ensure sanitization policies apply retroactively to legacy content.

### 4.6. Cost-Reconciled Infrastructure Budget ($2,476.00/Month)

The platform operates on a fully reconciled, high-availability, production-grade AWS infrastructure budget of **$2,476.00/month**:

| Component / Service | AWS Instance / Type | HA Topology & Scale Details | Monthly Cost (USD) |
| :--- | :--- | :--- | :--- |
| **AWS Aurora PostgreSQL** | Serverless v2 | Multi-AZ (0.5 to 8 ACUs per AZ) | $440.00 |
| **Redis Cluster** | `cache.m6g.large` | 1 Primary, 2 Replica Nodes | $297.84 |
| **Envoy RLS Redis** | `cache.t4g.medium` | 1 Primary, 1 Replica (Dedicated) | $68.00 |
| **Redpanda Cluster** | `im4g.xlarge` | 3 Dedicated Brokers with local NVMe SSDs | $812.16 |
| **App Compute (EKS)** | `m6g.xlarge` | 3 Dedicated Worker Nodes | $570.00 |
| **EKS Control Plane** | AWS Flat Fee | Fully Managed EKS Kubernetes Cluster | $73.00 |
| **Network & Transit** | NAT + VPC Endpoints | S3 Gateway Endpoint + Topology-Aware Routing | $120.00 |
| **EBS Storage (gp3)** | Block Storage | Optimized GP3 Volumes | $45.00 |
| **S3 Storage & Glacier** | S3 Standard/Glacier | Tiered Archives & Redpanda S3 Shadow Buckets | $50.00 |
| **TOTALS** | | **Production HA Environment Baseline** | **$2,476.00 / month** |

---

## 5. Complete Functional Requirements (User Stories)

### 5.1. Epic: Multi-Tenant Workspace & Security
*   **US-101 (Tenant Separation):** As a user, I want the system to enforce strict separation of my workspaces, so that Client A can never access tasks belonging to Client B.
    *   *Acceptance Criteria:* Database queries must run with PostgreSQL Row-Level Security (RLS) active. Attempting to bypass RLS via parameter manipulation must result in an immediate `403 Forbidden` response.
*   **US-102 (Asymmetric JWT Validation):** As an API developer, I want the gateway to authenticate requests using stateless asymmetric JWTs, so that we avoid high-frequency database sessions checks.
    *   *Acceptance Criteria:* The system validates RS256 JWTs against a dynamic JWKS endpoint with a cached TTL of 24 hours. Unknown `kid`s must trigger a single-flight, non-blocking background fetch while blocking parallel spam lookups.

### 5.2. Epic: High-Performance Data Sync & Output
*   **US-201 (Real-Time Board Broadcast):** As a collaborative user, I want task board moves to reflect instantly on my screen, so that I can see my team's progress without refreshing.
    *   *Acceptance Criteria:* The real-time synchronization must utilize persistent WebSockets over Elixir channels, delivering payload updates in **sub-100ms** at the client edge.
*   **US-202 (Background Connection Preservation):** As a mobile user, I want the application to stop sending telemetry updates when my app is backgrounded, so that my battery and data plan are preserved.
    *   *Acceptance Criteria:* Backgrounded tabs enter a 5-minute passive validation phase. Outbound pushes of task payloads are blocked; only `"token_required"` control frames are sent.

### 5.3. Epic: Event Distribution & Storage Resiliency
*   **US-301 (Transactional Outbox Deliveries):** As an SRE, I want database updates to trigger outbox events atomically, so that we guarantee zero event loss between our database and the event streaming tier.
    *   *Acceptance Criteria:* Updates use a transactional outbox model. The outbox recovery workers run in an active-active `replicas: 2` deployment using `FOR UPDATE SKIP LOCKED`.
*   **US-302 (Tombstone Deletions):** As an auditor, I want any physical deletion of database records to be logged to a tombstone tracker, so that we maintain complete history compliance.
    *   *Acceptance Criteria:* A database-level trigger intercepts physical deletions and writes the table name, record ID, and workspace ID to a `deleted_tombstones` table.

---

## 6. Implementation Tasklist (Chronological & Sequential)

```
================──────────────────────────────────────────────────────────────────────────────
                                 PHASE 1: CLOUD INFRASTRUCTURE & MESH
================──────────────────────────────────────────────────────────────────────────────

[1.1] Setup VPC and Private Subnets with Route Tables
      - Provision VPC across 3 Availability Zones (AZs) in AWS.
      - Configure public subnets with 2 High-Availability NAT Gateways.
      - Set up private subnets for application and database resources.
      - Link: Section 6.1 (Network & Transit Budget).

[1.2] Deploy AWS S3 VPC Gateway Endpoint
      - Provision an S3 VPC Gateway Endpoint inside private route tables to bypass NAT Gateway processing charges.
      - Link: Section 2.3 (Tiered Storage S3 Endpoints).

[1.3] Provision AWS EKS Cluster
      - Create an EKS cluster with 3 dedicated `m6g.xlarge` worker nodes.
      - Enforce a DaemonSet and system resource boundary limiting application allocations to 75% of node capacity.
      - Link: Section 4.5 (EKS Compute Node Sizing).

[1.4] Install Linkerd Service Mesh
      - Install Linkerd CLI and deploy Linkerd control plane with mutual TLS (mTLS) enabled.
      - Configure mutating webhook failure policies: 'Ignore' for system namespaces, 'Fail' for the 'platform' namespace.
      - Link: Section 1.2 (Mesh Deadlock Protection).

================──────────────────────────────────────────────────────────────────────────────
                                  PHASE 2: DATABASE & CACHING TIER
================──────────────────────────────────────────────────────────────────────────────

[2.1] Provision AWS Aurora Serverless v2 PostgreSQL
      - Provision a Multi-AZ Aurora PostgreSQL v2 cluster scaling dynamically between 0.5 and 8 ACUs.
      - Enable logical replication and configure a PgBouncer connection pool tier in Transaction Mode.
      - Link: Section 2.1 (AWS Aurora Serverless v2).

[2.2] Configure Multi-Tenant Row-Level Security (RLS)
      - Apply `ALTER TABLE ENABLE ROW LEVEL SECURITY` on core tables (tasks, projects).
      - Implement security policies using `current_setting('app.current_workspace_id')`.
      - Link: Section 2.1.2 (PostgreSQL RLS configuration).

[2.3] Deploy Redis Cluster (v7.2)
      - Provision an AWS ElastiCache Redis cluster (`cache.m6g.large`, 1 Primary, 2 Replicas).
      - Provision a dedicated rate-limiting Redis instance (`cache.t4g.medium`).
      - Link: Section 6.1 (Redis Cluster Cost allocations).

[2.4] Set WAL Safety Retention Caps
      - Run database commands to configure the physical slot sync caps:
        `ALTER SYSTEM SET max_slot_wal_keep_size = '10240MB';`
      - Link: Section 2.3 (WAL Disk Space Safeguards).

================──────────────────────────────────────────────────────────────────────────────
                              PHASE 3: BACKEND SERVICES (GO API & OUTBOX)
================──────────────────────────────────────────────────────────────────────────────

[3.1] Statically Compile Go Command & Query Services
      - Embed the timezone database using `_ "time/tzdata"`.
      - Build multi-stage, rootless Dockerfiles utilizing `gcr.io/distroless/static-debian12`.
      - Link: Section 6.2.1 (Go Production Dockerfile).

[3.2] Implement Dual-Pool Database Client in Go
      - Initialize PgBouncer Write Pool in Go using `QueryExecModeSimpleProtocol`.
      - Initialize Direct-to-Reader Read Pool using client-cached prepared statements.
      - Link: Section 2.1.1 (High-Performance Dual-Pool Go Configuration).

[3.3] Implement Tenant-Isolated RLS Context Middleware
      - Create Go middleware to extract claims from contexts, verify membership, and set session variables inside transactions.
      - Link: Section 2.1.1 (ExecuteTenantTransaction).

[3.4] Implement Go Singleflight with Detached Contexts
      - Implement a `detachedContext` helper and route database query fallbacks through a singleflight group.
      - Link: Section 2.2 (Query Coalescing via Singleflight).

[3.5] Deploy the Active-Active Outbox Recovery Worker
      - Build a continuous recovery worker using `FOR UPDATE SKIP LOCKED`.
      - Configure worker to run outside open transactions.
      - Deploy as a Kubernetes Deployment with `replicas: 2`.
      - Link: Section 6.3 (Continuous Outbox Worker Deployment).

================──────────────────────────────────────────────────────────────────────────────
                           PHASE 4: REAL-TIME SYNC & WEBSOCKET ENGINE (ELIXIR)
================──────────────────────────────────────────────────────────────────────────────

[4.1] Setup Elixir Sync Service Build Infrastructure
      - Install `build-base`, `git`, and `openssl-dev` in the builder stage.
      - Build dynamic, non-root Alpine runtime images with explicit directory ownership.
      - Link: Section 6.2.2 (Elixir Production Dockerfile).

[4.2] Implement Dynamic, exit-trapping Revocation Consumer
      - Inject `Process.flag(:trap_exit, true)` into the `init/1` block of `RealtimeSync.RevocationConsumer`.
      - Implement `terminate/2` to trigger `XGROUP DESTROY` on Redis.
      - Link: Section 3.2 (Clean Redis Consumer Group Deregistration).

[4.3] Configure Finch HTTP Client Pools
      - Register the Finch client pool in the application supervisor tree.
      - Link: Section 3.2 (Supervised Finch Instance Isolation).

[4.4] Implement Non-Blocking JWKS Resolver
      - Create a GenServer that delegates network fetches to dynamic tasks.
      - Implement negative caching with a maximum size check (10,000 entries) and a 5-second cooldown.
      - Link: Section 3.1 (Non-Blocking Background JWKS Resolver).

[4.5] Implement Nil-Safe, Validated Trace Context Parsing
      - Validate incoming `traceparent` WebSockets payloads against the W3C spec regex.
      - Link: Section 3.3 (Nil-Safe OpenTelemetry Trace Extraction).

================──────────────────────────────────────────────────────────────────────────────
                             PHASE 5: BOUNDARY SECURITY & LOGISTICS
================──────────────────────────────────────────────────────────────────────────────

[5.1] Deploy Envoy API Gateway and Global Rate Limiter
      - Install Envoy and the rate-limiting gRPC service.
      - Configure local rate limit limits alongside the global RLS Redis instance.
      - Link: Section 4.1 (Fail-Open Global Rate Limiting).

[5.2] Configure Goldmark & Bluemonday Write-Path Sanitization
      - Configure Go to compile raw markdown on write using `goldmark`.
      - Apply strict UGC HTML sanitization using `bluemonday` to prevent XSS.
      - Link: Section 4.2 (Dual-Control OWASP XSS Protection).

[5.3] Register Active Lua Consumer Reaper Script in Redis
      - Upload the Lua script to the Redis cluster.
      - Schedule a cron or worker to execute the script hourly, verifying PEL status before group deletion.
      - Link: Section 3.2 (Active Lua Consumer Reaper Script).

[5.4] Deploy Two-Tier OpenTelemetry Collector
      - Deploy OTel collector agents as a DaemonSet with Trace ID routing.
      - Deploy the OTel collector gateway as a stateful Deployment with a `tail_sampling` processor.
      - Link: Section 5.1 (Unified OpenTelemetry DaemonSet with OOM Guards).

[5.5] Establish ArgoCD & External Secrets Operator Integration
      - Install ArgoCD and the External Secrets Operator.
      - Set up SecretStores to pull environment variables dynamically from AWS Secrets Manager.
      - Link: Section 6.3.2 (Kubernetes Schema Migration Job Configuration).
```