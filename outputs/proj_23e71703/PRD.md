# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Concept: Single-User Task Management Webapp (High-Performance Engine)

---

## 1. Goal Description & Business Alignment

### 1.1 Vision
To deliver a highly responsive, real-time, single-user task management web application capable of sub-100ms interaction latencies (such as rapid drag-and-drop actions, status toggling, and fast creation workflows). 

By leveraging a high-performance, single-writer state engine on the backend, the application bypasses the overhead of traditional distributed multi-user databases. It achieves infinite horizontal scaling through an isolated multi-tenant architecture, with one dedicated, encrypted database per user.

### 1.2 Core Architectural Philosophy
*   **Decoupled High-Performance Write Engine**: Functional Core, Imperative Shell pattern using stateless FastAPI workers on the front end, coordinated by a high-throughput Redis event queue and session synchronizer.
*   **Isolated Multi-Tenancy**: Complete filesystem and cryptographic isolation. Each user possesses a single database file, eliminating cross-tenant data leakage risks and query indexing performance degradation.
*   **Zero-Trust Security Baseline**: Strong security guarantees including SQLCipher database-level encryption at rest, memory zeroization, strict directory containment (path traversal protection), and cryptographically signed OAuth2 JWT session management.

---

## 2. Target Persona & Use Cases

### 2.1 Target Persona: "The High-Velocity Power User"
*   **Profile**: Professionals, developers, and project managers who work at high speed. They demand near-instantaneous UI responses, rely on multiple simultaneously open browser tabs, and expect offline resilience with automatic state synchronization.
*   **Key Pain Points**: Lagging user interfaces during rapid reordering, data synchronization conflicts across browser tabs, and privacy concerns regarding personal tasks stored in shared databases.

### 2.2 Core Use Cases

#### UC-1: Rapid Task Reordering (Drag-and-Drop)
The user rearranges tasks on their board. The system reorders elements instantly in the UI, calculates a floating-point sequence index, transmits the mutation, and updates other open tabs in real-time via Server-Sent Events (SSE) without page refreshes.

#### UC-2: Concurrent Multi-Tab Operations
The user has their task list open on both their laptop and desktop monitors. When a task is checked off on the laptop, the desktop screen updates within <50ms without initiating a manual reload.

#### UC-3: High-Frequency Bulk Actions
The user multi-selects and updates 50 tasks simultaneously (e.g., changing status to "Completed"). The UI processes this as a single atomic visual update, and the API buffers the operations safely without triggering database lock contentions or resource exhaustion.

---

## 3. Functional Requirements

### 3.1 Task & Workspace Domain Model

```
+-----------------------------------------------------------------+
|                           WORKSPACE                             |
|  - workspace_id (UUID, Default implicit workspace for user)     |
+-----------------------------------------------------------------+
                                |
                                | 1
                                |
                                | 0..*
                                v
+-----------------------------------------------------------------+
|                             TASK                                |
|  - task_id (UUID String, PK)                                    |
|  - title (String, Max 255 chars)                                |
|  - status (Enum: PENDING, IN_PROGRESS, COMPLETED)               |
|  - sequence_index (REAL, Float64 representation)                |
|  - version (Integer, Auto-increment, Optimistic Locking)        |
|  - completed_at (Nullable Epoch Timestamp)                      |
|  - updated_at (Epoch Timestamp)                                 |
+-----------------------------------------------------------------+
```

### 3.2 Workspace & Task Management (CRUD)
*   **FR-1.1**: The system shall support a single default Workspace per user.
*   **FR-1.2**: Users shall be able to create, read, update, and delete (CRUD) tasks.
*   **FR-1.3**: The system shall enforce a strict character limit of 255 characters on the task `title`.
*   **FR-1.4**: Tasks shall support three statuses: `PENDING`, `IN_PROGRESS`, and `COMPLETED`. Transitioning to `COMPLETED` must set the `completed_at` timestamp. Transitioning away from `COMPLETED` must nullify this field.

### 3.3 Real-Time State Synchronization & Reordering
*   **FR-2.1**: The system shall support arbitrary reordering of tasks using a floating-point sequence index (`sequence_index`). The client calculated value must allow O(1) inserts between any two tasks (e.g., target sequence = $(prev.sequence + next.sequence) / 2.0$).
*   **FR-2.2**: The backend shall expose a Server-Sent Events (SSE) endpoint to stream real-time task modifications to all active browser tabs of the authenticated user.
*   **FR-2.3**: Every write API mutation must yield a state event sent to the user's Redis Pub/Sub stream, which is immediately broadcasted via the SSE connection manager.

### 3.4 Conflict Resolution (Optimistic Version Locking)
*   **FR-3.1**: Every task payload returned to the UI must include an integer `version` field.
*   **FR-3.2**: When writing updates via `PATCH /api/v1/tasks/{task_id}`, the client must submit the current known version.
*   **FR-3.3**: The server shall compare the client-provided version with the database-level version. If the client-provided version is outdated, the update must be rejected with an HTTP `409 Conflict` status, and the latest server-side database state must be pushed to the client via the active SSE stream.

---

## 4. Non-Functional Constraints & Security Engineering

### 4.1 Security & Isolation Architecture

```
                    [ TLS 1.3 Terminated at Nginx Ingress ]
                                      |
                     [ API Gateway: Token Verification ]
                     (Validate JWT Signature & Blacklist)
                                      |
                    [ Stateless FastAPI Worker Nodes ]
         (Fetch Decryption Key from Secrets Manager with 5m Memory Cache)
                                      |
         +----------------------------+----------------------------+
         | (Local Decrypted Workspace)                             | (Direct Sync Pipeline)
         v                                                         v
  [ Node-Local NVMe SSD ]                                 [ Redis Cluster (TLS 1.3) ]
  - Enforced Hash-based Directory                         - Token Bucket Rate Limiter
  - SQLCipher Encrypted File                              - Event Streams (AOF Everysec)
  - max_page_count Quota (~500MB)                         - Pub/Sub Channel per User
```

#### NFC-1.1: Cryptographic Path Isolation (IDOR / Path Traversal Defenses)
The backend must decouple system paths from client-provided user IDs. The file system path for a user's database must be dynamically resolved using a SHA-256 hash of their verified system identifier, distributed into a nested directory structure.

```python
# Standardized Secure Path Resolution
import hashlib
from pathlib import Path

BASE_DATA_DIR = Path("/data/tenants").resolve()

def get_secure_user_db_path(user_id: str) -> Path:
    tenant_hash = hashlib.sha256(user_id.encode('utf-8')).hexdigest()
    # Path layout: /data/tenants/ab/cd/abcdef12345...db
    depth_path = BASE_DATA_DIR / tenant_hash[:2] / tenant_hash[2:4] / f"{tenant_hash}.db"
    
    if not depth_path.resolve().is_relative_to(BASE_DATA_DIR):
        raise PermissionError("Path traversal attempt detected and blocked.")
    return depth_path.resolve()
```

#### NFC-1.2: SQLCipher Database-Level Encryption at Rest
*   All user database files must be encrypted with AES-256-CBC using SQLCipher.
*   Decryption keys must be fetched dynamically from Vault/Secrets Manager during session initiation and cached locally in-memory with a strict 5-minute TTL.
*   The application must perform explicit cryptographic memory zeroization of the keys when closing connections.

#### NFC-1.3: DoS & Resource Exhaustion Defenses
*   **SQLite Engine Page Limits**: The SQLite connection must enforce hard file limits. Under database initialization:
    ```sql
    PRAGMA max_page_count = 131072; -- Strictly limits database size to 512MB
    ```
*   **Ingress Limits**: Nginx must drop request payloads exceeding 10MB (`client_max_body_size 10M`).
*   **Token Bucket Rate Limiting**: Limit API operations to a maximum of 60 write requests per 60 seconds per user token, implemented via Redis.

#### NFC-1.4: Compliance & Cryptographic Deletion (GDPR Alignment)
Every user's backups must reside in a dedicated AWS S3 prefix encrypted with a dedicated customer-managed AWS KMS key. Upon receiving a "Right to be Forgotten" deletion request, the user's database file is deleted from local storage, and their dedicated KMS key is deleted. This cryptographically shreds all immutable historical backups instantly.

### 4.2 SRE & Performance Requirements

#### NFC-2.1: Key Latency & Reliability SLOs
*   **Write Latency (P95)**: <150ms for REST PATCH/POST updates.
*   **Event Sync Latency (P95)**: <50ms from local Redis stream arrival to SSE client push.
*   **API Error Rate**: <0.1% failed requests (HTTP 5xx) over any rolling 30-day window.
*   **RPO (Recovery Point Objective)**: Strictly <1.0 second. This is achieved by writing transaction payloads to a Redis Append-Only File (AOF) configured with `appendfsync everysec` prior to returning an HTTP `200/202` response.

#### NFC-2.2: Ephemeral Local NVMe & WAL Streaming
*   Stateless FastAPI nodes shall write directly to high-speed local instance-store NVMe SSDs (`/dev/nvme0n1`) in SQLite WAL (Write-Ahead Logging) mode. This avoids network file locking issues associated with EFS/Ceph.
*   An independent background process (e.g., Litestream) must stream WAL commits continuously to S3 to guarantee point-in-time recovery without blocking API request-response loops.

---

## 5. Technical Implementation Tasklist

This section outlines the step-by-step horizontal roadmap to build, secure, and deploy the Single-User Task Management Webapp.

### Phase 1: Local Storage Engine & Security Foundations
1. Implement the SHA-256 hash-based nested path resolution algorithm in Python, ensuring complete path containment validation.
2. Configure the SQLCipher connection lifecycle, including fetching keys from simulated mock Secrets Manager endpoints and implementing memory zeroization routines.
3. Define the core SQLite database schema using migration scripts, including strict constraints (`CHECK` constraints on status, version increments, and sequence ranges).
4. Configure connection pools to enforce a single write connection per user database file, preventing local lock-contention exceptions.
5. Create a unit testing suite that verifies that SQLCipher database files cannot be read without the correct cryptographic key.

### Phase 2: Core API & State Machine Construction
6. Develop FastAPI routing endpoints for task CRUD operations, validating input payloads via strict Pydantic schemas.
7. Build the optimistic version locking validation engine within database transactional boundaries.
8. Integrate local SQLite database operations with the Redis Event Streaming architecture (pushing mutations to Redis Streams on write transactions).
9. Write the API payload logic that returns HTTP `202 Accepted` or `200 OK` only after the Redis Stream registers and acknowledges the event with `appendfsync everysec` enabled.
10. Implement sliding-window Token Bucket rate limiting in FastAPI via Redis Lua scripts.

### Phase 3: Real-Time Sync & Multi-Tab Core
11. Build the Server-Sent Events (SSE) FastAPI connection routing layer.
12. Build the single-use ticket system (Ticket-Granting Token) for the browser SSE handshake. This authorizes connection upgrades using a short-lived, 10-second token passed through query parameters, avoiding raw JWT leaks in HTTP logs.
13. Wire the SSE endpoint to subscribe to the user-specific Redis Pub/Sub channel.
14. Construct the event dispatch mechanism to broadcast incoming task modifications to all connected SSE channels.
15. Implement browser-level integration testing to verify that concurrent tabs synchronize UI changes in <50ms during rapid task drag-and-drop actions.

### Phase 4: Production Resilience & Infrastructure Configuration
16. Write Terraform scripts to provision memory-optimized Redis Cluster nodes (Graviton AWS `cache.r7g.large` instances) with transit and rest encryption enabled.
17. Author Nginx ingress configurations that enforce SSL/TLS 1.3 termination, set security headers (CSP, X-Frame-Options, X-Content-Type-Options), and limit request payloads.
18. Configure a background streaming tool (such as Litestream) to track SQLite WAL files on local NVMe drives and replicate transaction chunks to S3.
19. Define S3 lifecycle rules and individual KMS key mappings per user prefix, establishing the mechanism for cryptographic deletion.
20. Set up structured JSON logging throughout the application using `structlog`, injecting correlation IDs, user IDs, and database metrics.

### Phase 5: CI/CD & Progressive Deployment
21. Set up GitHub Actions CI pipelines to run lints, perform security checks, run unit tests, and build Docker images.
22. Configure ArgoCD tracking to manage stateful caching environments and deployment pipelines.
23. Draft Argo Rollout manifest definitions using Canary release methodologies (progressive scaling from 10% to 50% to 100%).
24. Author Prometheus Metric Analysis rules that query HTTP 5xx rates and latency budgets during canary evaluations.
25. Conduct automated end-to-end chaos tests (e.g., node crashes, Redis failovers) to verify that recovery behaviors align with RPO <1.0s and SLO availability commitments.