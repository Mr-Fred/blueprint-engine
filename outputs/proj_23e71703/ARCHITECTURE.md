# ARCHITECTURE.md: PRODUCTION-READY SYSTEM ARCHITECTURE
## System Concept: Single-User Task Management Webapp (High-Performance, Multi-Tenant Partitioned Architecture)

---

## 1. Paradigm & Style (Hexagonal & Functional Core)

The application is structured using a **Hexagonal (Ports & Adapters) Architecture** combined with a **Functional Core, Imperative Shell** execution pattern. This decouples the pure core domain logic (task state changes, transitions, sequence calculation) from side effects (database persistence, SSE streaming, authentication providers, and network events).

### 1.1 Architectural Pattern & Flow of Control

```
                              [ Incoming Web Traffic ]
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │                Nginx Ingress                  │
                 │         (SSL/TLS, Rate Limiter, mTLS)         │
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼ (HTTP/2, gRPC, WSS)
                 ┌───────────────────────────────────────────────┐
                 │          FastAPI Web Nodes (Adapters)         │
                 │   - Decouple Requests & Validate Schemas      │
                 │   - Handle App-Level Route Routing            │
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │                               Application Core                                │
 │                                                                               │
 │     ┌──────────────┐         ┌─────────────────┐         ┌──────────────┐     │
 │     │ Primary Port │ ──────> │ Use Case / App  │ ──────> │ Secondary    │     │
 │     │  (Inbound)   │         │ Service Layer   │         │ Port (Out)   │     │
 │     └──────────────┘         └────────┬────────┘         └──────┬───────┘     │
 │                                       │                         │             │
 │                                       ▼                         │             │
 │                              ┌─────────────────┐                │             │
 │                              │  Pure Domain    │                │             │
 │                              │  Entities       │                │             │
 │                              │ (Functional Core)                │             │
 │                              └─────────────────┘                │             │
 └─────────────────────────────────────────────────────────────────┼─────────────┘
                                                                   │
                                         ┌─────────────────────────┴─────────────┐
                                         │                                       │
                                         ▼                                       ▼
                         ┌───────────────────────────────┐       ┌───────────────────────────────┐
                         │     Infrastructure Adapter    │       │     Infrastructure Adapter    │
                         │    [Redis Stream (Transient)] │       │     [SQLCipher (Persistent)]  │
                         └───────────────────────────────┘       └───────────────────────────────┘
```

*   **Functional Core**: The core entities and domain services (e.g., executing a state transition on a Task, recalculating the `sequence_index` floating-point ordering) contain no network, database, or logging side effects. They are purely functional, deterministic, and highly testable.
*   **Imperative Shell**: The FastAPI Adapters and CLI Entrypoints act as the Shell. They manage network protocols, parse inputs, query HashiCorp Vault for cryptographic keys, fetch the state from SQLCipher/Redis, pass pure data structures to the Domain Core, receive the updated state, and commit the changes back to persistence.
*   **Decoupled Concurrency Loop**: Instead of standard distributed multi-user locks, single-user performance is optimized via a **Single-Writer Actor Loop per user session** hosted inside memory using Redis Streams. This guarantees instant UI response times without lock contention.

---

## 2. Database Schema & Scaling Topology

To scale to millions of users while maintaining high performance, the architecture isolates every single user's dataset into a dedicated **SQLCipher database file**. Network-attached POSIX-locking architectures (e.g., mounting raw SQLite over AWS EFS or Ceph) are strictly prohibited due to write locking failures, corruption risks, and network latency. 

We utilize **local ephemeral NVMe instance SSDs** for the hot-path write/read database transactions, coupled with an asynchronous, transactional WAL-replication engine (using **Litestream**) to continuously stream modified WAL frames to encrypted AWS S3 buckets.

### 2.1 Storage Architecture Topology

```
                  ┌──────────────────────────────────────────────────────────┐
                  │                 FastAPI App Node Pod                     │
                  │                                                          │
                  │   ┌──────────────────────────────────────────────────┐   │
                  │   │        Local Ephemeral SSD Disk (/dev/nvme0)     │   │
                  │   │                                                  │   │
                  │   │   /data/tenants/ab/cd/[hash_id].db               │   │
                  │   │   - SQLCipher AES-256 Encrypted                  │   │
                  │   │   - WAL Journal Mode Enabled                     │   │
                  │   └────────┬─────────────────────────────────────────┘   │
                  └────────────┼─────────────────────────────────────────────┘
                               │
                               │ (Continuous Frame-level Replication)
                               ▼
                  ┌──────────────────────────────────────────────────────────┐
                  │             Litestream Replication Daemon                │
                  └────────────┬─────────────────────────────────────────────┘
                               │
                               │ (TLS 1.3 Outbound Stream)
                               ▼
                  ┌──────────────────────────────────────────────────────────┐
                  │                AWS S3 Object Storage                     │
                  │    - Versioned S3 Bucket (PITR Enabled)                  │
                  │    - KMS Key-per-Tenant Storage Isolation                │
                  └──────────────────────────────────────────────────────────┘
```

### 2.2 SQLCipher Database Schema

This schema is initialized inside each individual user `.db` file on dynamic creation.

```sql
-- Database initialization schema for SQLCipher user databases
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA max_page_count = 131072; -- Enforces hard limit of ~512MB per user database

CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT PRIMARY KEY NOT NULL CHECK (length(workspace_id) <= 64),
    name TEXT NOT NULL CHECK (length(name) <= 100),
    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY NOT NULL CHECK (length(task_id) <= 64),
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (length(title) <= 255),
    description TEXT CHECK (length(description) <= 2000),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED')),
    sequence_index REAL NOT NULL, -- Floating-point index for O(1) drag-and-drop reordering
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    completed_at INTEGER, -- Epoch seconds
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_workspace_status ON tasks(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_sequence ON tasks(workspace_id, sequence_index);
```

---

## 3. Security & IAM Model

The security model assumes a zero-trust network environment. It combines identity protection, isolation, path-traversal blocking, and explicit cryptographic controls.

```
+──────────────────────────┐
│ Client (WSS / HTTPS / SSE)
+─────────────┬────────────+
              │
              ▼ (TLS 1.3)
+──────────────────────────┐
│ Nginx Edge Gateway       ├──────[ Decrypts TLS & Validates IP / Rate-Limits ]
+─────────────┬────────────+
              │
              ▼ (Internal App Network via mTLS)
+──────────────────────────┐
│ FastAPI Application Node ├──────[ 1. Verifies signed JWT Claim ]
│                          ├──────[ 2. Zero-Trust SHA-256 Hash Path Generation ]
│                          ├──────[ 3. Dynamic SQLCipher Key Retrieval via KMS/Vault ]
+─────────────┬────────────+
              │
              ▼ (In-Memory Isolation / Encrypted Connection)
+──────────────────────────┐
│ Dedicated SQLite Memory  ├──────[ Cryptographic Memory Zeroization on Close ]
+──────────────────────────┘
```

### 3.1 Zero-Trust Path Resolution Pattern

To fully eliminate IDOR (Insecure Direct Object Reference) and Path Traversal vulnerabilities, user IDs are never parsed as raw paths. The system hashes the user identification string to generate a predictable, safe, two-tier nested directory structure on the ephemeral filesystem.

```python
import hashlib
from pathlib import Path

BASE_DATA_DIR = Path("/data/tenants").resolve()

def get_secure_user_db_path(user_id: str) -> Path:
    """
    Translates a verified user ID into a deterministic, secure path.
    Completely eliminates Path Traversal vulnerabilities by using SHA-256 hashes
    and enforcing sub-directory confinement validation.
    """
    if not user_id:
        raise ValueError("User ID cannot be empty.")
        
    # Generate static 64-character hex hash
    tenant_hash = hashlib.sha256(user_id.encode('utf-8')).hexdigest()
    
    # Nested 2-tier bucket directory (e.g. /data/tenants/ab/cd/abcdef123...)
    depth_dir = BASE_DATA_DIR / tenant_hash[:2] / tenant_hash[2:4]
    user_db_path = (depth_dir / f"{tenant_hash}.db").resolve()
    
    # Enforce containment restriction
    if not user_db_path.is_relative_to(BASE_DATA_DIR):
        raise PermissionError("Path containment violation detected.")
        
    return user_db_path
```

### 3.2 Dynamic Key Retrieval & Cryptographic Memory Zeroization

Upon connection, the SQLCipher master decryption key is fetched from Vault and mapped to memory. To prevent cross-tenant key leakage inside long-running Python worker processes, keys are explicitly cleared from memory immediately after the connection is established.

```python
import ctypes
import pysqlite3 as sqlite3

def zeroize_string(target_str: str) -> None:
    """
    Overwrites the memory space of a sensitive key string with zero-bytes.
    Prevents lingering key material in Python's garbage-collected memory space.
    """
    location = id(target_str) + 20  # Fast pointer access to raw buffer offset in CPython
    size = len(target_str)
    ctypes.memset(location, 0, size)

def open_secure_db_connection(user_id: str, key_material: str) -> sqlite3.Connection:
    """
    Opens an encrypted SQLCipher connection and immediately zeroizes the ephemeral key variable.
    """
    db_path = get_secure_user_db_path(user_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    # Pass SQLCipher Key
    conn.execute(f"PRAGMA key = '{key_material}';")
    
    # Verify the database connection works and is authenticated
    try:
        conn.execute("SELECT count(*) FROM sqlite_master;")
    except sqlite3.DatabaseError as e:
        conn.close()
        raise PermissionError("Database decryption failed. Invalid key material.") from e
    finally:
        # Guarantee secure wipe of key material from process heap
        zeroize_string(key_material)
        
    return conn
```

### 3.3 GDPR "Right To Be Forgotten" Cryptographic Shredding Pattern
Every tenant has a unique KMS Key Alias assigned in AWS KMS or HashiCorp Vault. Under GDPR compliance, when a user requests deletion:
1. The tenant-specific KMS Key is permanently deleted from the Key Management System.
2. The user's active S3 backup files and local NVMe `.db` files become instantly and permanently unrecoverable, completing the deletion requirement across all backups and historical replication logs.

---

## 4. SRE, Observability, & SLOs

Our production targets are aligned to maintain high performance with strict recovery point objective (RPO) and recovery time objective (RTO) metrics.

### 4.1 Production SLO Target Metrics

| Service Level Indicator (SLI) | SLO Metric Target | Measurement Boundary |
| :--- | :--- | :--- |
| **Write API Latency** | $\le 100\text{ms}$ (P95), $\le 250\text{ms}$ (P99) | 5-minute rolling average |
| **Read Engine Latency** | $\le 15\text{ms}$ (P95) | 5-minute rolling average |
| **System Uptime** | $\ge 99.99\%$ Availability | Monthly calendar window |
| **Max Data Loss Window (RPO)**| $\le 1.0\text{ second}$ data loss | System/Infrastructure outage |
| **System Recovery Time (RTO)**| $\le 30.0\text{ seconds}$ database restoration | Total node disaster scenario |

### 4.2 Production Observability Implementation (Structured Logging)

The application utilizes structured JSON logs processed by unified aggregators. Every HTTP request injects and correlates a tracking span.

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# Usage Example:
# logger.info("database_transaction_committed", user_id="usr_94a2b", duration_ms=14.2)
```

### 4.3 GitOps Canary Release Configuration

Canary rollouts are managed via Argo Rollouts, dynamically analyzing error rates before scaling deployment groups.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: task-management-engine
spec:
  replicas: 12
  strategy:
    canary:
      analysis:
        templates:
          - templateName: telemetry-error-analysis
      steps:
        - setWeight: 10
        - pause: { duration: 10m }
        - setWeight: 50
        - pause: { duration: 5m }
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: telemetry-error-analysis
spec:
  metrics:
  - name: error-rate
    successCondition: "result[0] < 0.001" # Less than 0.1% errors
    provider:
      prometheus:
        address: http://prometheus.monitoring.svc:9090
        query: |
          sum(rate(http_requests_total{status=~"5.."}[2m])) 
          / 
          sum(rate(http_requests_total[2m]))
```

---

## 5. API Definitions & Protocol Contracts

Communication interfaces are strictly split: **HTTP/2 RESTful endpoints** handle mutating transactional actions, and **Server-Sent Events (SSE)** handle real-time downstream synchronization.

### 5.1 Mutating Write Contracts (HTTP/2 REST)

#### Create / Update Task Interface
*   **Protocol**: `HTTP/2` over TLS 1.3
*   **Path**: `PATCH /api/v1/tasks/{task_id}`

```json
{
  "workspace_id": "ws_8192a0",
  "title": "Migrate system databases to SQLCipher clustered engines",
  "description": "Perform validation and runtime zeroization of internal key structures",
  "status": "IN_PROGRESS",
  "sequence_index": 1402.5,
  "version": 42
}
```

*   **Optimistic Concurrency Control**: The `version` parameter is matched inside the database write transaction. If the target database version differs from the version provided by the client, the transaction aborts with a `409 Conflict` code, forcing the client to pull the latest state before attempting another edit.

### 5.2 Server-Sent Events Real-Time Read Stream (SSE)

To establish the Server-Sent Events real-time sync channel, clients must first exchange their JWT credentials for a short-lived Single-Use Ticket Code (SUTC). This prevents credential leakage inside browser URL Query strings.

```
Client                     FastAPI Gateway                Redis Pub/Sub
  │                             │                              │
  ├─(1) POST /auth/ticket ─────>│                              │
  │     [Header: Bearer JWT]    │                              │
  │                             │                              │
  │<─(2) Returns Short-lived ───│                              │
  │      Ticket (10s TTL)       │                              │
  │                             │                              │
  ├─(3) GET /api/v1/sync/stream?ticket=sutc_abc123 ───────────>│
  │                             │                              │
  │                             ├─(4) Verifies ticket in Cache │
  │                             │                             │
  │                             ├─(5) Subscribes to Channel ──>│
  │                             │     "user_updates_94a2b"     │
  │                             │                              │
  │<─(6) Streams Events ────────┼──────────────────────────────┤
```

#### Downstream SSE Event Stream Payload
```sse
event: task_mutation
id: 1700000021
data: {
  "task_id": "t_948a20bc",
  "workspace_id": "ws_8192a0",
  "title": "Migrate system databases to SQLCipher clustered engines",
  "status": "IN_PROGRESS",
  "sequence_index": 1402.5,
  "version": 42,
  "updated_at": 1700000021
}
```

This streaming real-time contract ensures that multiple open tabs of the same single user instantly maintain a synchronized interface state, driven dynamically by changes processed in the actor core.