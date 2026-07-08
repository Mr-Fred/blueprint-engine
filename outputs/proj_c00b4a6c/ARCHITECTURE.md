# Architecture Blueprint: High-Performance AI Meal Planner
**System Class:** Highly Scalable, Event-Driven, Mobile-First AI Assistant  
**Platform Target:** Google Cloud Platform (GCP) & Google Kubernetes Engine (GKE)

---

## 1. Clean / Hexagonal System Architecture

The core engineering pattern decouples business domain logic from transport protocols, external LLM APIs, and specific storage technologies. Go microservices are structured using Clean/Hexagonal principles, separating layers into Domain, Use Cases (Ports), and Adapters (Infrastructure).

### 1.1 Architectural Domain Layout

```
                  +-------------------------------------------------+
                  |                   Infrastructure (Adapters)     |
                  |                                                 |
                  |   +------------------+     +----------------+   |
                  |   | Apigee/gRPC In   |     | Memorystore Out|   |
                  |   +--------+---------+     +-------+--------+   |
                  |            |                       ^            |
                  |            |                       |            |
                  |            v                       |            |
                  |      +-----+-----------------------+-----+      |
                  |      |       Application (Ports)         |      |
                  |      |                                   |      |
                  |      |   +---------------------------+   |      |
                  |      |   |   MealPlannerUseCase      |   |      |
                  |      |   +-------------+-------------+   |      |
                  |      |                 |                 |      |
                  |      +-----------------+-----------------+      |
                  |                        |                        |
                  |                        v                        |
                  |                  +-----+------+                 |
                  |                  |   Domain   |                 |
                  |                  |  (Entities)|                 |
                  |                  +------------+                 |
                  |            +                       |            |
                  |            |                       v            |
                  |   +--------v---------+     +-------+--------+   |
                  |   | Cloud SQL Adapter|     | Pub/Sub Out    |   |
                  |   +------------------+     +----------------+   |
                  +-------------------------------------------------+
```

### 1.2 Component Directory Mapping (Go Services)
To enforce layer decoupling, codebases strictly map to the following directory boundaries:

```filepath
/cmd
  /server                  # Application entry point (dependency injection, wireup)
/internal
  /domain                  # Rich domain models, entities, & core domain errors (no external imports)
    /meals
    /users
  /ports                   # Use-cases (inward ports) and repository interfaces (outward ports)
    repositories.go        # Interface defining database access
    usecases.go            # Interface defining business operations
  /adapters                # Implementation-specific details (infrastructure)
    /db                    # Cloud SQL / PGX driver connection & query execution
    /cache                 # Memorystore Redis connection & Bloom filter checks
    /pubsub                # Cloud Pub/Sub publishing logic
    /grpc                  # gRPC transport controllers & interceptor wiring
```

---

## 2. Database Schema & Scaling Topology

To secure sensitive Health/Metric PII under global compliance regulations (GDPR/CCPA) and support fast lookups, we implement **Envelope Encryption** paired with a **Versioned, Salted Blind Index Pattern**. This configuration isolates user lookup hashes from their ciphertexts, preventing pattern extraction.

### 2.1 Database Topology & DR Specifications
*   **Primary Tier:** Google Cloud SQL for PostgreSQL configured with **REGIONAL High Availability** (Synchronous multi-zone replication with automatic failover).
*   **Secondary Tier:** Cross-region Asynchronous Read Replicas.
*   **DR Metrics:** 
    *   *User Profiles & Target Goals:* RTO: 30 minutes (automatic multi-zone, DNS-routed cross-region promotion), RPO: 1 minute.
    *   *Meal Plans & Groceries:* RTO: 1 hour, RPO: 15 minutes.
*   **DR Safeguards:** If async replication lag crosses a strict threshold, write operations in the primary region degrade gracefully into read-only modes, prompting a client-facing degraded state instead of crashing Go connection pools.

### 2.2 Relational Schema Definition (DDL)

```sql
-- Core User Table
CREATE TABLE users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL,                         -- Envelope-encrypted ciphertext
    email_salt BYTEA NOT NULL,                   -- Unique salt per row to prevent pattern extraction
    email_blind_index_version SMALLINT NOT NULL, -- Identifies pepper version used from Secret Manager
    email_blind_index CHAR(64) NOT NULL,         -- salted HMAC-SHA256 (email + salt + pepper)
    name TEXT NOT NULL,                          -- Envelope-encrypted ciphertext
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_users_email_blind ON users(email_blind_index, email_blind_index_version);

-- User Goals Profile Table
CREATE TABLE user_goals (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    target_calories INTEGER NOT NULL CHECK (target_calories > 0),
    diet_goal TEXT NOT NULL CHECK (diet_goal IN ('weight_loss', 'muscle_gain', 'maintenance')),
    excluded_ingredients TEXT[] NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_goals_excluded ON user_goals USING GIN (excluded_ingredients);

-- Wrapped DEK Storage Directory (Isolated Cryptographic Store for Secure Erasure)
CREATE TABLE user_cryptographic_keys (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    wrapped_dek BYTEA NOT NULL,                  -- Local Data Encryption Key wrapped by GCP KMS KEK
    key_version VARCHAR(50) NOT NULL,            -- KMS Key Version
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Meal Plans Table
CREATE TABLE meal_plans (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    plan_date DATE NOT NULL,
    -- JSONB Schema Validation is strictly enforced at use-case layers
    meals JSONB NOT NULL CONSTRAINT check_meals_json_type CHECK (jsonb_typeof(meals) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_meal_plans_user_date ON meal_plans (user_id, plan_date);
CREATE INDEX idx_meal_plans_meals_gin ON meal_plans USING GIN (meals);

-- Inventory Table
CREATE TABLE inventory_items (
    item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available' CONSTRAINT check_item_status CHECK (status IN ('available', 'depleted')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_active_inventory_low_stock 
ON inventory_items (user_id, status) 
WHERE status = 'depleted';
```

---

## 3. Security, IAM & Compliance Model

This architecture operates on a **Zero-Trust Network Pattern**, ensuring no backend pod has broad system access. 

```
                                      [Apigee Edge]
                                            |
                                            | Issues Internal signed JWT (15m)
                                            v
                                     [GKE Pod Ingress]
                                            |
                                            | Anthos Service Mesh (mTLS / SPIFFE)
                                            v
                                  [Go Downstream Pods]
                                     |             |
                 Reads/Writes DB    |             | Publishes Event
                                     v             v
                              [Cloud SQL]    [Cloud Pub/Sub]
                                                   |
                                                   | OIDC Push / Pull subscription
                                                   v
                                        [Python AI Worker Pod]
                                                   |
                                                   | Blocked from PostgreSQL & User Svcs
                                                   +------------------------------------+
                                                   | - GKE NetPol Egress restricted     |
                                                   | - Egress Proxy Domain Filter      |
                                                   +------------------+-----------------+
                                                                      |
                                                                      v
                                                              [Vertex AI / LLM]
```

### 3.1 Network Isolation & Access Policies
*   **Kubernetes NetworkPolicies:** The `python-ai-worker` pod is isolated inside a hardened namespace. It is blocked from connecting to Cloud SQL and Core User services. 
*   **SSRF Mitigation:** Egress from the worker pod is locked down. Outbound traffic must route through an `egress-proxy` (running Envoy) that decrypts TLS, verifies SNI, and enforces domain whitelisting strictly limited to Vertex AI endpoints (`*.googleapis.com`).
*   **DNS Filtering:** coreDNS firewalls block outgoing queries from the GKE cluster to unauthorized, untrusted domains to stop DNS data-tunneling/exfiltration.

### 3.2 Dynamic Audience & Scope Check Interceptor (Go)
To prevent internal token replay attacks across microservices, downstream services must validate the audience (`aud`) and scopes (`scp`) of signed internal context tokens, and immediately fail on misconfiguration.

```go
package interceptors

import (
	"context"
	"log"
	"os"
	"strings"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

type TokenValidator struct {
	expectedAudience string
}

func NewTokenValidator() *TokenValidator {
	aud := os.Getenv("EXPECTED_AUDIENCE")
	if aud == "" {
		// FAIL-FAST: Prevent silent environment deployment misconfiguration
		log.Fatalf("[FATAL] Security misconfiguration: EXPECTED_AUDIENCE environment variable is empty.")
	}
	return &TokenValidator{expectedAudience: aud}
}

func (tv *TokenValidator) UnaryInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return nil, status.Error(codes.Unauthenticated, "missing metadata")
	}

	authHeader := md.Get("authorization")
	if len(authHeader) == 0 {
		return nil, status.Error(codes.Unauthenticated, "missing token")
	}

	tokenStr := strings.TrimPrefix(authHeader[0], "Bearer ")
	claims, err := verifyAndParseInternalJWT(tokenStr) // Cryptographically validates KMS signature
	if err != nil {
		return nil, status.Error(codes.Unauthenticated, "invalid token signature")
	}

	// Validate Dynamic Target Audience
	if claims.Audience != tv.expectedAudience {
		return nil, status.Error(codes.PermissionDenied, "audience mismatch")
	}

	// Validate Scopes
	hasScope := false
	for _, s := range claims.Scopes {
		if s == "meal_plans:write" {
			hasScope = true
			break
		}
	}
	if !hasScope {
		return nil, status.Error(codes.PermissionDenied, "insufficient privileges")
	}

	return handler(ctx, req)
}
```

### 3.3 GDPR Crypto-Shredding Design
To satisfy the GDPR *Right to Be Forgotten* (Art. 17) while retaining immutable backups on Google Cloud Storage (WORM, 365 days retention lock), the system performs **Cryptographic Erasure (Crypto-Shredding)**:
1. When a user requests deletion, their record is removed from the primary Cloud SQL instance.
2. The user's specific wrapped DEK stored in the isolated `user_cryptographic_keys` table is permanently deleted.
3. This deletes the key needed to decrypt the user's data. GCS ciphertext remains permanently unreadable (un-decryptable), satisfying GDPR requirements.
4. **IAM Separation:** GKE workload identity restricts `roles/cloudkms.cryptoKeyDecrypter` access to the dedicated User Service pod. The Python AI Worker explicitly lacks this permission.

---

## 4. SRE, Observability & SLO Model

We enforce strict reliability metrics, distributed trace propagation, and robust backoff policies to handle transient failures gracefully.

### 4.1 Global Trace Context Propagation Engine
We propagate distributed tracing across synchronous and asynchronous barriers using **OpenTelemetry W3C Trace Context headers**.

```
Request -> Apigee Gateway (Inject Traceparent)
              |
              v (gRPC Metadata)
       Meal Planner Svc
              |
              v (Pub/Sub Message Attributes: traceparent)
       Cloud Pub/Sub Event Bus
              |
              v (Pull Subscription)
       Python AI Worker Svc
              |
              v (W3C Header)
       Vertex AI API / LLM
```

### 4.2 SRE SLI/SLO Targets

| Service Boundary | Service Level Indicator (SLI) | Service Level Objective (SLO) |
| :--- | :--- | :--- |
| **Apigee API Gateway** | Availability: % of gRPC / HTTP requests returning status `OK` / `2xx` over a 30-day window. | $\ge 99.9\%$ |
| **Go Microservices** | Latency: % of synchronous database queries and validation checks completing in $\le 150\text{ms}$. | $\ge 95\%$ |
| **AI Orchestration Svc** | Latency: % of end-to-end meal plan generation jobs completing in $\le 45\text{ seconds}$. | $\ge 90\%$ |
| **GKE Pub/Sub Pipeline** | Reliability: Messages routed to the Dead Letter Queue (DLQ) vs total published messages. | $\le 0.5\%$ |

### 4.3 Database Adaptive Connection Pooling (Go Adapter)
This Go adapter initializes a connection pool with adaptive connection lifecycles and utilizes `gobreaker` to shield services during Cloud SQL failovers.

```go
package database

import (
	"database/sql"
	"log"
	"time"

	"github.com/sony/gobreaker"
	_ "github.com/jackc/pgx/v5/stdlib"
)

type SafeDB struct {
	DB *sql.DB
	CB *gobreaker.CircuitBreaker
}

func InitPool(dsn string) *SafeDB {
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		log.Fatalf("Unable to connect to database: %v", err)
	}

	// Resilient connection parameters
	db.SetMaxOpenConns(150)                // Balanced capacity for custom-4 instance
	db.SetMaxIdleConns(50)
	db.SetConnMaxLifetime(3 * time.Minute) // Limits stale connection lifetime during zonal failover
	db.SetConnMaxIdleTime(1 * time.Minute)

	// Configure Circuit Breaker for DB operations
	cbSettings := gobreaker.Settings{
		Name:        "PostgreSQL-Connection-Pool",
		MaxRequests: 5,
		Interval:    10 * time.Second,
		Timeout:     30 * time.Second,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 10 && failureRatio > 0.5
		},
	}
	cb := gobreaker.NewCircuitBreaker(cbSettings)

	return &SafeDB{DB: db, CB: cb}
}
```

---

## 5. API Contracts & Non-Blocking Async Orchestration

### 5.1 Protobuf Contract Schema: `meal_planner.proto`

```protobuf
syntax = "proto3";

package mealplanner.v1;

option go_package = "github.com/mealplanner/api/v1;v1";

service MealPlannerService {
  rpc GenerateWeeklyMealPlan (GenerateWeeklyMealPlanRequest) returns (GenerateWeeklyMealPlanResponse);
  rpc GetFridgeSuggestions (GetFridgeSuggestionsRequest) returns (GetFridgeSuggestionsResponse);
}

message GenerateWeeklyMealPlanRequest {
  string diet_goal = 1;         // e.g. "weight_loss", "muscle_gain"
  int32 target_calories = 2;
  repeated string excluded_ingredients = 3;
}

message GenerateWeeklyMealPlanResponse {
  string job_id = 1;
  string status = 2;            // "queued" or "processing"
  int64 estimated_duration_ms = 3;
}

message GetFridgeSuggestionsRequest {
  repeated string current_fridge_items = 1;
}

message RecipeSuggestion {
  string recipe_title = 1;
  repeated string matching_ingredients = 2;
  repeated string missing_ingredients_to_buy = 3;
  int32 prep_time_minutes = 4;
}

message GetFridgeSuggestionsResponse {
  repeated RecipeSuggestion suggestions = 1;
}
```

### 5.2 Non-Blocking Python AI Worker Integration
The Python AI Orchestrator consumes events asynchronously from Pub/Sub. Key secrets (such as the Vertex AI key) are retrieved dynamically using a non-blocking asynchronous client, and validation errors reject messages directly to a Dead Letter Queue (DLQ).

```python
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
from google.cloud import secretmanager_v1beta1 as secretmanager
from prometheus_client import Counter

logger = logging.getLogger("meal_planner")

# Metric cardinality protection mapping
class MetricsSafety:
    ALLOWED_EXCEPTIONS = {
        ValidationError: "validation_error",
        asyncio.TimeoutError: "timeout_error",
        ConnectionError: "connection_error",
        ValueError: "value_error"
    }

    @classmethod
    def get_sanitized_label(cls, exc: Exception) -> str:
        for exc_class, label in cls.ALLOWED_EXCEPTIONS.items():
            if isinstance(exc, exc_class):
                return label
        return "generic_system_error"

fallback_counter = Counter(
    "ai_worker_fallback_total",
    "Total fallback events executed due to schema/LLM failures",
    labelnames=["reason"]
)

class RecipeSchema(BaseModel):
    recipe_title: str = Field(..., max_length=100)
    prep_time_minutes: int = Field(..., ge=1, le=1440)
    matching_ingredients: list[str] = Field(..., max_length=50)
    missing_ingredients_to_buy: list[str] = Field(..., max_length=50)

    class Config:
        extra = "forbid"

class AsyncSecretCache:
    """Thread-safe, non-blocking TTL secret retrieval cache."""
    def __init__(self, secret_id: str, ttl_seconds: int = 300):
        self.client = secretmanager.SecretManagerServiceAsyncClient()
        self.secret_id = secret_id
        self.ttl = ttl_seconds
        self._secret: Optional[str] = None
        self._last_fetched: float = 0.0
        self._lock = asyncio.Lock()

    async def get_secret(self) -> str:
        async with self._lock:
            now = time.time()
            if not self._secret or (now - self._last_fetched) > self.ttl:
                response = await self.client.access_secret_version(
                    request={"name": self.secret_id}
                )
                self._secret = response.payload.data.decode("UTF-8").strip()
                self._last_fetched = now
            return self._secret

async def process_worker_event(record_value: str) -> Dict[str, Any]:
    try:
        validated_data = RecipeSchema.model_validate_json(record_value)
        return validated_data.model_dump()
    except Exception as e:
        logger.error(
            "Payload validation failed. Nacking message to Pub/Sub DLQ.",
            exc_info=True,
            extra={"raw_payload": record_value}
        )
        reason_label = MetricsSafety.get_sanitized_label(e)
        fallback_counter.labels(reason=reason_label).inc()
        # Raise explicitly to nack the message and route to DLQ
        raise ValueError("Invalid payload schema. Aborting execution.") from e
```

---

## 6. Infrastructure as Code & GitOps Automation

### 6.1 GKE KEDA Autoscale Configuration
This configures scaling based directly on Cloud Pub/Sub backlog metrics, bypassing Prometheus scraping latency while mitigating rate limits (HTTP 429).

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: python-ai-worker-scaler
  namespace: mealplanner
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: python-ai-worker
  minReplicaCount: 2
  maxReplicaCount: 16 # Capped to avoid exceeding downstream Vertex AI API quotas
  cooldownPeriod: 300 # Cool down slowly to prevent thrashing
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 0
          policies:
          - type: Percent
            value: 100 # Double capacity aggressively on queue spikes
            periodSeconds: 15
        scaleDown:
          stabilizationWindowSeconds: 300 # Slow scale down step window
  triggers:
  - type: gcp-pubsub
    metadata:
      subscriptionName: projects/mealplanner-prod/subscriptions/job-created-sub
      subscriptionSize: "20"
```

### 6.2 ArgoCD GitOps DB Migration Dry-Run Integration
To safely coordinate schema updates with application deployments, we use an **ArgoCD PreSync Hook** to validate backwards-compatible migrations prior to rollout.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: schema-migration-dryrun
  namespace: mealplanner
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  template:
    spec:
      containers:
      - name: migrator-dryrun
        image: us-central1-docker.pkg.dev/mealplanner-prod/app/db-migrator:latest
        command: ["/app/migrate", "up", "--dry-run"]
      restartPolicy: OnFailure
```

### 6.3 Secure Terraform Provisioning Module
This module deploys GKE Workload Identity bindings, provisions Cloud SQL with regional High Availability, and configures the Pub/Sub Dead Letter Queue (DLQ).

```hcl
# GKE Workload Identity IAM Binding for GSA-to-KSA Mapping
resource "google_service_account" "ai_worker_sa" {
  account_id   = "ai-worker-sa"
  display_name = "AI Worker Service Account (No Direct Key Decryption Admin Access)"
}

resource "google_project_iam_member" "wi_binding" {
  project = "mealplanner-prod"
  role    = "roles/iam.workloadIdentityUser"
  member  = "serviceAccount:mealplanner-prod.svc.id.goog[mealplanner/python-ai-worker-sa]"
}

# KMS Key Viewer permission only.
# The AI Worker explicitly lacks decryption permissions (cryptoKeyDecrypter) to ensure key isolation.
resource "google_cloud_kms_crypto_key_iam_member" "kms_decrypter_binding" {
  crypto_key_id = "projects/mealplanner-prod/locations/us-central1/keyRings/mealplanner-ring/cryptoKeys/profile-dek-kek"
  role          = "roles/cloudkms.viewer"
  member        = "serviceAccount:${google_service_account.ai_worker_sa.email}"
}

# High-Availability Cloud SQL PostgreSQL Primary DB
resource "google_sql_database_instance" "postgres_primary" {
  name             = "mealplanner-prod-pg"
  database_version = "POSTGRES_15"
  region           = "us-central1"

  settings {
    tier              = "db-custom-4-16384" # Memory-optimized Custom SQL Core
    availability_type = "REGIONAL"          # Synchronous multi-zone HA replication

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = "projects/mealplanner-prod/global/networks/mealplanner-vpc"
    }
  }
}

# Pub/Sub Infrastructure with Dead Letter Queue (DLQ)
resource "google_pubsub_topic" "job_created_dlq" {
  name = "job-created-dead-letter"
}

resource "google_pubsub_subscription" "job_created_sub" {
  name  = "job-created-sub"
  topic = "job-created"

  message_retention_duration = "604800s" # 7 days retention

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.job_created_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  depends_on = [google_pubsub_topic.job_created_dlq]
}
```