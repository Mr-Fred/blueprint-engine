# Product Requirements Document (PRD)

## High-Throughput Collaborative Design Whiteboard with Canvas Synchronization
**Project ID:** `proj_f6f64ca7`  
**Document Version:** 1.0.0-Release  
**Author:** Principal Product Owner  
**Status:** Approved for Core Engineering Implementation  

---

## 1. Goal Description & Mission Synthesis

### 1.1. Executive Summary & Mission Statement
Modern collaborative design platforms require ultra-low latency canvas synchronization combined with military-grade security and highly predictable operational cost modeling. Legacy solutions fail under enterprise load because of heavy Operational Transformation (OT) synchronization overhead, massive cloud egress fees from real-time websocket broadcasts, and exposure to targeted Denial of Service (DoS) attacks.

The mission of this project is to build a **High-Throughput Collaborative Design Whiteboard** that guarantees sub-50ms canvas synchronization for up to **20,000 concurrent active users** ($100,000$ messages/sec peak write load) while maintaining strict zero-trust security boundary enforcement. 

### 1.2. Core Technical Strategy
To achieve these goals, we reject OT in favor of **Delta-state Conflict-free Replicated Data Types (CRDTs)**, decouple real-time transient operations from transactional metadata, and implement a **Cloudflare Zero-Egress Hybrid Topology**.

```
+-------------------------------------------------------------------------------------------------+
|                                  STATEFUL ZONE-AWARE EDGE LAYER                                 |
|                                                                                                 |
|   +------------------------------------+              +-------------------------------------+   |
|   | Envoy Proxy Ingress Gateway        |              |       Lyft Rate Limit Service       |   |
|   | - Native JWT Verification          |              | - Centralized Rate Limiter          |   |
|   | - Per-Client Local Rate Limiter    |<------------>| - Fails Open (Protected by Gateway) |   |
|   +----------------+-----------------+-+              +------------------+------------------+   |
|                    |                 |                                   |                      |
|                    | (mTLS / SPIFFE) +----------(gRPC RateLimit)---------+                      |
|                    v                                                     v                      |
|   +----------------+-------------------+              +------------------+------------------+   |
|   |    Go Room Coordinator Instance    |              |       ELASTICACHE VALKEY            |   |
|   | - Live SVID Stream Reloading      |              | - Centralized Rate Limit Values     |   |
|   | - Schema-Aware Proto Validator     |<------------>| - Stateful Nonce Registry (2x TTL)  |   |
|   +----------------+-------------------+              +-------------------------------------+   |
|                    |                                                                            |
+--------------------|----------------------------------------------------------------------------+
                     | (Async Parallel Read)
                     v
         +-----------+-----------+
         |  SCYLLA NO-SQL CLUST  |
         | - TWCS & 3-Day Temp TTL|
         | - Synthetic Sharding  |
         +-----------+-----------+
                     | (Cold Startup Offload)
                     v
         +-----------+-----------+
         |  CLOUDFLARE R2 BUCKET |
         | (Zero Egress Snapshot)|
         +-----------------------+
```

*   **In-Memory Hot Path:** Valkey Sorted Sets (ZSET) track connection states with $O(\log N)$ pruning complexity, eliminating CPU spikes during client reconnect loops.
*   **Persistent Warm Path:** ScyllaDB utilizes **Time Window Compaction Strategy (TWCS)** and a strict 3-day Time-To-Live (TTL) configuration. This eliminates the creation of row-level tombstones and prevents read-latency spikes.
*   **Cold Archival Path:** An asynchronous background worker consolidates active canvases and offloads snapshot archives to **Cloudflare R2** prior to ScyllaDB TTL expiry, achieving zero-egress backup storage.
*   **Perimeter Hardening:** Cryptographic JWT validation occurs natively at the Envoy Ingress edge. Envoy applies an inline Lua filter to generate signed headers with SHA256 HMAC tokens, using a shared secret injected securely via Kubernetes secrets. Downstream Go applications verify these tokens in constant-time.

---

## 2. Target Persona & Detailed Use Cases

### 2.1. Target Personas
```
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│       The Design Professional        │  │      The System Administrator        │  │      The Security Architect          │
│             (Creative)               │  │             (Operator)               │  │             (SecOps)                 │
├──────────────────────────────────────┤  ├──────────────────────────────────────┤  ├──────────────────────────────────────┤
│ "I need smooth, sub-50ms vector path │  │ "I need zero-downtime rolling deploys│  │ "I need absolute assurance against   │
│ synchronization and real-time cursor │  │ with zero connection drops, and      │  │ session replays, canonical spoofing, │
│ feedback during large design storms  │  │ highly predictable infra billing."   │  │ and CPU-inflation parsing attacks."  │
│ without board-load stutters."        │  │                                      │  │                                      │
└──────────────────────────────────────┘  └──────────────────────────────────────┘  └──────────────────────────────────────┘
```

### 2.2. Product Use Cases
*   **Use Case 1: Real-Time Enterprise Brainstorming (The Stroke-Storm)**  
    Fifty design professionals connect to a single canvas, drawing, commenting, and dropping vector elements simultaneously. The system must process and broadcast their cursor positions and vector modifications with $<50\text{ms}$ end-to-end synchronization latency.
*   **Use Case 2: Zero-Downtime Infrastructure Rolling Upgrades (The Invisible Handoff)**  
    System operators trigger a production deployment during peak hours. The Kubernetes Horizontal Pod Autoscaler (HPA) and the Go Room Coordinator must execute a 5-minute phased, jittered client eviction loop. Sockets are systematically disconnected and redirected to new replicas using random delays ($15\text{s}$ to $90\text{s}$) to avoid thundering herd storms.
*   **Use Case 3: Anti-Replay Session Hydration (The Resilient Handshake)**  
    An enterprise designer's laptop experiences a transient network dropout on a train. As they reconnect, the system verifies their identity. The handshake verifier uses Valkey to validate their nonce within a strict 60-second window ($2 \times \text{AllowedClockDriftSeconds}$). This blocks replay attacks while immediately restoring their active whiteboard session.

---

## 3. Complete Functional Requirements

### 3.1. Real-Time Vector & Canvas State Synchronization (FR-1)
*   **FR-1.1:** The sync plane must utilize State-based or Delta-state **Conflict-free Replicated Data Types (CRDTs)** (Yjs/Automerge) to handle out-of-order execution and guarantee eventual consistency across all distributed clients without central lock routing.
*   **FR-1.2:** Dynamic interactions (e.g., cursor paths and transient coordinates) must bypass permanent disk storage and route exclusively through the in-memory **ElastiCache Valkey** tier to minimize I/O write amplification.
*   **FR-1.3:** Serialization must utilize highly optimized **Protocol Buffers v3** over WebSockets with HTTP/3 WebTransport fallbacks. Raw, uncompressed JSON frames are strictly prohibited in the real-time path.

### 3.2. Secure Perimeter & Single-Gateway JWT Authentication (FR-2)
*   **FR-2.1:** Cryptographic signature verification of OIDC JWT tokens must be centralized at the **Envoy Ingress Edge** via the `envoy.filters.http.jwt_authn` filter. Downstream Go applications must be protected from double-verification CPU waste.
*   **FR-2.2:** Envoy must compute a secure SHA256 HMAC signature of the authenticated user's `sub` claim and inject it into downstream headers (`X-User-Authenticated-ID` and `X-Gateway-Validation-Signature`).
*   **FR-2.3:** Downstream Go application containers must validate the Envoy signature using constant-time comparison (`subtle.ConstantTimeCompare`) against a shared secret loaded securely via read-only Kubernetes Secrets mounted at `/etc/gateway/secrets/hmac-key`.
*   **FR-2.4:** Communications between the Envoy Edge and downstream Room Coordinator Pods must utilize **strict Mutual TLS (mTLS)**. Workload identities must be dynamically rotated and verified using **SPIFFE/SPIRE SVID certificates** hot-reloaded in memory via the SPIFFE Workload API Go SDK.

### 3.3. Replay Protection & Anti-Replay Nonce Verification (FR-3)
*   **FR-3.1:** To prevent state-pollution and nonce-exhaustion DoS attacks, the Go Room Coordinator must execute cryptographic signature validation **before** writing, querying, or mutating state in any caching or storage layer.
*   **FR-3.2:** Nonces must be validated against duplicate reuse using Valkey `SET NX` command executions with a TTL set to **60 seconds** ($2 \times \text{AllowedClockDriftSeconds} = 60\text{s}$) to secure the entire $[-30\text{s}, +30\text{s}]$ clock drift window.
*   **FR-3.3:** The application must explicitly parse the response of the Valkey `SET NX` execution. Handshake requests must be rejected immediately if the command returns a null reply or if the status is not `"OK"`.

### 3.4. O(log N) Connection Tracking & Lockout Prevention (FR-4)
*   **FR-4.1:** Active socket tracking must utilize **Valkey Sorted Sets (ZSETs)** to keep socket pruning complexity bounded at $O(\log N)$.
*   **FR-4.2:** Active connection timestamps must be evaluated using Valkey's native, monotonic clock source (`redis.call('TIME')`) inside the Lua transaction script, neutralizing distributed server clock-drift vulnerabilities.
*   **FR-4.3:** The connection tracker must enforce a limit of **3 concurrent active connections per user**. Stale connections must be cleaned up automatically during connection acquisition, preventing user lockouts on unclean socket drops.

### 3.5. Stampede-Resistant JWKS Cache Engine (FR-5)
*   **FR-5.1:** The Go Room Coordinator must manage JWKS cache-miss fetches globally by using `singleflight.Group` keyed to a static string `"jwks_refresh"`. This prevents concurrent outbound HTTP storms to the IdP during key rotations.
*   **FR-5.2:** Unknown or malicious Key IDs (`kid`) must be registered inside a thread-safe `LRUNegativeCache` map bounded by a strict ceiling of **10,000 entries** to prevent Out-of-Memory (OOM) memory exhaustion.
*   **FR-5.3:** The `LRUNegativeCache` must utilize internal `sync.RWMutex` locking to prevent Go runtime pointer corruption during concurrent read-write map updates.

### 3.6. Schema-Aware Defensive Protobuf Validation (FR-6)
*   **FR-6.1:** To prevent CPU-exhaustion and Protobuf-bomb attacks (CWE-400), the Go Coordinator must parse incoming binary streams recursively **only** inside specific schema-defined sub-message field tags (e.g., Field Tag `10` for CRDT nested nodes).
*   **FR-6.2:** Speculative, recursive parsing of opaque length-delimited fields (Wire Type 2) such as raster images or drawings is strictly prohibited. These fields must be skipped directly using wire type definitions.
*   **FR-6.3:** The Protobuf parser must cast length fields to unsigned 32-bit integers (`uint32`) and verify that index pointer operations do not overflow or bypass total message boundaries, eliminating negative integer overflow infinite-loop exploits.
*   **FR-6.4:** Any unhandled or unexpected client-to-server payload frame types (such as `ServerGoAwayFrame` or `AuthChallengeFrame`) must be rejected by a strict default catch-all block inside the sanitization loop.

### 3.7. Tiered Storage & Zero-Egress Snapshot Archival (FR-7)
*   **FR-7.1:** Active delta changes must be written to ScyllaDB with an optimized **3-day Time-to-Live (TTL)** (`default_time_to_live = 259200`) using the **Time Window Compaction Strategy (TWCS)** with 1-day windows.
*   **FR-7.2:** ScyllaDB must be configured with `PasswordAuthenticator` enabled. All database connections must authenticate using secure credentials injected via Kubernetes Secrets.
*   **FR-7.3:** To prevent data loss, a background worker must continuously capture active canvases, generate consolidated binary snapshots, and archive them to **Cloudflare R2** before the 3-day ScyllaDB TTL expires.
*   **FR-7.4:** The ScyllaDB table `gc_grace_seconds` must be set to 3 days ($259,200\text{ seconds}$), aligned with an automated rolling repair execution every 12 hours via Scylla Manager, eliminating the risk of zombie data resurrections.

### 3.8. Segregated Telemetry & Dynamic Logging Controls (FR-8)
*   **FR-8.1:** Prometheus metric scraping and health handlers must run on an isolated, internal telemetry port `:9090`, preventing public exposure.
*   **FR-8.2:** Port `9090` must be protected by a strict Kubernetes `NetworkPolicy`, allowing ingress only from authorized Prometheus scraping nodes.
*   **FR-8.3:** The telemetry port must expose an administrative POST handler (`/admin/log-level`) allowing operators to dynamically swap the runtime logging level (e.g., `WARN` to `DEBUG`) using token-based Bearer authentication. Input levels must be validated against a strict whitelist.

---

## 4. Non-Functional Constraints

### 4.1. Performance & Latency SLA (NFR-1)
*   **NFR-1.1:** Average end-to-end canvas synchronization latency (from client action to remote render) must remain **under 50ms** under peak load.
*   **NFR-1.2:** Cold room boot startup recovery (retrieving the base snapshot from Cloudflare R2 and replaying remaining ScyllaDB deltas) must complete **under 200ms**.

### 4.2. Scalability & Autoscaling Bounds (NFR-2)
*   **NFR-2.1:** The architecture must scale horizontally to support up to **20,000 concurrent active users** distributed across 1,333 active rooms.
*   **NFR-2.2:** Kubernetes Pod autoscaling must utilize a **Horizontal Pod Autoscaler (HPA)** scaling dynamically between **2 and 12 replicas** based on CPU utilization (target $60\%$) and active connection counts (target 1,000 connections/pod).

### 4.3. Go Memory Optimization & Container Hardening (NFR-3)
*   **NFR-3.1:** To prevent container OOM-kills, the Go runtime must be configured with `GOMEMLIMIT=3400MiB` (85% of the hard 4GiB container limit) and `GOGC=100`, forcing garbage collection before cgroup boundaries are reached.
*   **NFR-3.2:** Containers must be executed using the **Exec Form** (`CMD ["/app/room-coordinator"]`) to ensure signal propagation. They must run with non-root privileges (`runAsNonRoot: true`) and a read-only root filesystem (`readOnlyRootFilesystem: true`).

### 4.4. Cost-Efficiency & FinOps Guardrails (NFR-4)
*   **NFR-4.1:** The baseline multi-AZ production infrastructure cost must remain **under $1,900.00/month** for up to 50,000 monthly active users.
*   **NFR-4.2:** Real-time egress fees must be bounded at **$0.00** by routing all traffic via Cloudflare Tunnels and archiving assets to Cloudflare R2 (Bandwidth Alliance zero-egress paths).
*   **NFR-4.3:** To prevent runaway APM costs, the OpenTelemetry Collector must be configured with a **0.1% head-based probabilistic sampler** for transaction-level traces, while logging levels default to `WARN`.

---

## 5. Numbered, Horizontal Implementation Tasklist

This section defines the chronological, step-by-step roadmap required to take this system from Day-1 scaffolding to production verification.

| Task # | Phase | Component | Detailed Description | Security/Resilience Guardrail | Acceptance Criteria |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | Phase 1: Day-1 | Local Dev | Deploy local `docker-compose` environment configuring ScyllaDB restricted to 750MB RAM on a local `tmpfs` volume and Valkey in LRU eviction mode. | Ensure developers do not experience thermal throttling; limit Scylla memory footprint to 1.5GB total dev system draw. | Local container stack boots in under 15 seconds; CQL schema compiles successfully. |
| **2** | Phase 1: Day-1 | Datastores | Initialize ScyllaDB production tables with Time Window Compaction Strategy (TWCS) and `gc_grace_seconds` set to 3 days ($259,200\text{s}$). Enable `PasswordAuthenticator`. | Prevent zombie data reappearance and eliminate row-level tombstones. | CQL schema verified on 3-node cluster; authentication successfully enforced. |
| **3** | Phase 2: Ingress | Ingress Gate | Configure Envoy Proxy listeners on port 443 with native JWT authentication mapping the verified `sub` claim to the `X-User-Authenticated-ID` header. | centrale perimeter security; block unauthenticated traffic at the gateway. | JWT validation successfully blocks invalid tokens; verified headers are passed downstream. |
| **4** | Phase 2: Ingress | Ingress Gate | Implement the Lyft gRPC Rate Limit Service (RLS) cluster inside Envoy and configure local token bucket fallback rate limiters using client-IP descriptors. | Prevent rate limiter fail-open cascading crashes and block global listener-level lockouts. | Local rate limits trigger per client IP if RLS fails open; Envoy fails open gracefully. |
| **5** | Phase 2: Ingress | Ingress Gate | Build Envoy dynamic header injection filter using Lua to sign downstream headers with a SHA256 HMAC token. | Secure downstream claims; prevent internal header spoofing. | Envoy injects valid `X-Gateway-Validation-Signature` headers into requests. |
| **6** | Phase 3: Handshake | App Gateway | Implement constant-time HMAC validation inside the Go Coordinator to verify Envoy signatures against a read-only Kubernetes Secret key. | Protect Go Coordinator from unauthenticated requests and canonicalization bypasses. | Go Coordinator accepts Envoy signed requests and rejects manipulated header fields. |
| **7** | Phase 3: Handshake | App Gateway | Build the Replay Protection Engine. Verify signatures first, then execute Valkey `SET NX` with a 60s TTL (2x Allowed Clock Drift). | Block replay attacks and prevent Valkey state-pollution DoS attacks. | Valkey `SET NX` is executed after signature validation; duplicate nonces are rejected. |
| **8** | Phase 3: Handshake | Connection | Build the ZSET Valkey Connection Tracker using native Valkey TIME (`redis.call('TIME')`) and limit active sockets to 3 per user identity. | Neutralize clock drift and prevent user connection lockouts on transient drops. | Valkey tracking runs in $O(\log N)$ complexity; user connections above 3 are pruned. |
| **9** | Phase 4: Core App | JWKS Cache | Implement stampede-resistant JWKS Cache using a global singleflight key `"jwks_refresh"` and a thread-safe `LRUNegativeCache` bounded to 10k entries. | Protect external IdP from stampedes and prevent Go Coordinator OOM crashes. | JWKS misses are serialized; concurrent lookups for invalid `kid` keys are rejected. |
| **10** | Phase 4: Core App | Input Valid | Build the recursive Protobuf parser. Scan only explicit Field Tag `10` blocks and cast parsed lengths to `uint32`. | Prevent Protobuf-bomb CPU-inflation attacks (CWE-400) and integer overflow infinite loops. | Deeply-nested sub-messages are rejected; opaque Wire Type 2 fields are safely skipped. |
| **11** | Phase 4: Core App | Input Valid | Implement strict input sanitization on ScyllaDB partition-level bucket deletions, verifying room UUID structures. | Prevent SQL injection and unauthorized data modification/deletion. | Deletions fail if room ID does not conform to RFC-compliant UUID standards. |
| **12** | Phase 5: DevOps | Lifecycle | Mount the SPIRE Workload API Unix Domain Socket using the official SPIRE CSI driver inside the deployment manifest. | Enable zero-trust mTLS and support hot-reloading of short-lived SPIFFE SVID certificates. | Go Coordinator streams and hot-reloads certificates without requiring container restarts. |
| **13** | Phase 5: DevOps | Lifecycle | Configure the Go Room Coordinator's container with `GOMEMLIMIT=3400MiB` and set execution to the Exec Form (`CMD ["/app/room-coordinator"]`). | Prevent OOM-kills on sudden connection spikes and ensure correct `SIGTERM` signal propagation. | Container shuts down cleanly under `SIGTERM` and garbage collects memory at 85% limit. |
| **14** | Phase 5: DevOps | Lifecycle | Build the Go graceful eviction loop: close the listener first, run a 5-minute phased connection drain (5% batches), then trigger server shutdown. | Avoid thundering herd reconnect storms and prevent socket termination deadlocks. | Active sockets are evicted gradually; server shuts down cleanly within 6 minutes. |
| **15** | Phase 5: DevOps | CI/CD | Abstract database migration hosts into ConfigMaps and execute schema updates out-of-band via an ArgoCD PreSync Kubernetes Job. | Avoid database schema agreement failures during rolling deployments. | Schema migrations complete successfully prior to rolling container updates. |
| **16** | Phase 5: DevOps | Telemetry | Expose the Prometheus metrics scraping endpoint on an isolated internal port `:9090` and configure the logging syncer to target `stdout`. | Prevent ephemeral disk exhaustion and protect metrics from public ingress exposure. | Prom metrics are scraped on port 9090; logs stream asynchronously to stdout. |
| **17** | Phase 5: DevOps | Telemetry | Build the secure dynamic log-level endpoint on port `:9090` using Bearer Token authorization and a whitelist of permitted levels. | Allow dynamic logging level changes without exposing security configurations. | Log level updates require a valid Bearer token and input validation. |
| **18** | Phase 6: Release | Verification | Deploy a 0.1% head-based probabilistic sampler rule inside the OpenTelemetry Collector configuration. | Optimize tracing ingestion volumes and control SaaS monitoring costs. | Trace volume matches the 0.1% sampling rule; metrics are delivered successfully. |
| **19** | Phase 6: Release | Verification | Deploy the Kubernetes Horizontal Pod Autoscaler (HPA) configured to scale between 2 and 12 replicas. | Handle user storms dynamically and scale down automatically to save cost. | Pods scale up on load and scale down cleanly during off-peak hours. |
| **20** | Phase 6: Release | Chaos Test | Trigger high-concurrency connection flood attacks and sudden pod restarts using chaos testing tools. | Verify system resilience, anti-replay guards, and fail-open rate limiting. | System recovers under 200ms; duplicate nonces are blocked; database remains healthy. |