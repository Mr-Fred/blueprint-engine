# Product Requirements Document (PRD.md)

## 1. Goal Description

The AI Meal Planner Mobile App is a highly scalable, event-driven, mobile-first assistant designed to help users reach their target nutritional and dietary goals (such as fitness, fat loss, or muscle gain). The application automates the end-to-end weekly meal planning lifecycle, simplifies grocery inventory tracking through smart features like "fridge-to-plate" recipe suggestion, and enables users to contribute their custom homemade recipes. 

By utilizing Google Cloud Platform (GCP) serverless processing, a robust Go/Python microservice mesh, and advanced Large Language Model (LLM) orchestration, the platform delivers real-time, personalized nutrition assistance while maintaining enterprise-grade security and reliability.

---

## 2. Target Personas & Use Cases

### 2.1 Target Personas
*   **The Busy Fitness Enthusiast ("Alex"):** A corporate worker who trains 4–5 times a week. Alex needs strict, calorie-and-macro-accurate weekly meal plans that adapt to available ingredients to minimize meal prep stress.
*   **The Weight-Loss Tracker ("Sarah"):** A busy parent aiming to lose weight on a budget. Sarah wants to input leftover fridge ingredients to get instant, healthy recipes, reducing both food waste and grocery expenses.
*   **The Culinary Creator ("Marcus"):** A home cook who loves preparing homemade dishes. Marcus wants to log his custom recipes into the app, track their nutritional value, and blend them seamlessly into his automated weekly meal schedule.

### 2.2 Core Use Cases
*   **Weekly Goal-Driven Meal Planning:** A user inputs their dietary goals (e.g., *weight_loss*, *muscle_gain*, *maintenance*), target calories, and excluded ingredients. The system asynchronously generates a cohesive, nutritionally complete 7-day meal plan.
*   **Fridge-to-Plate Recommendations:** A user opens their "Digital Fridge" inside the app, selects currently available items (e.g., eggs, spinach, onions), and receives a list of immediate recipes they can prepare, along with a list of missing ingredients to buy.
*   **Custom Recipe Logging:** A user inputs their own homemade recipe steps, ingredients, and portions. The system processes the nutritional values and saves the recipe to the user's private library for future planning cycles.
*   **Integrated Grocery List Aggregation:** The application automatically consolidates missing ingredients from the active weekly meal plan and current depleted digital fridge inventory into a prioritized shopping list.

---

## 3. Complete Functional Requirements

### 3.1 User Onboarding & Goal Customization (Profile Service)
*   **F-101 (Dietary Profiles):** Users can define their high-level physical metrics, target calories, and primary nutritional goals (*weight_loss*, *muscle_gain*, *maintenance*).
*   **F-102 (Ingredient Exclusion):** Users can specify an array of excluded ingredients or allergens (e.g., *peanuts*, *gluten*, *shellfish*) which the system must exclude from all generated meals.
*   **F-103 (Envelope Encryption of PII):** All user-identifiable fields (such as `name` and `email`) must undergo application-layer envelope encryption using AES-256-GCM prior to database persistence.
*   **F-104 (Salted Blind Indexing):** To support O(1) database lookups on encrypted email addresses, the system must maintain a versioned, salted HMAC-SHA256 blind index column in a dedicated compound database index.

### 3.2 Automated Weekly Meal Planner (Meal Planner Service)
*   **F-201 (Async Plan Generation):** Requesting a 7-day plan triggers an asynchronous orchestration job via Google Cloud Pub/Sub, immediately returning a `202 Accepted` status code with a unique `job_id` and tracking context.
*   **F-202 (Real-Time Generation Status):** The mobile app must connect to a secure WebSocket service or utilize short-polling to display the real-time processing state ("Queued", "Generating", "Completed") of the pending meal plan.
*   **F-203 (Safe JSONB Persistence):** The generated meal plans must be validated and stored as a structured JSONB array in PostgreSQL, protected by application-level validation and structural integrity limits.
*   **F-204 (Custom Homemade Recipes):** Users can manually input custom recipes (title, ingredients, portions, cooking steps). The Go backend must persist these recipes to the relational database and compute estimated nutritional metrics.

### 3.3 Smart Fridge & Grocery Integration (Inventory Service)
*   **F-301 (Digital Fridge Inventory):** Users can log, update, and track items in their fridge. Items must support status transitions (`available`, `depleted`).
*   **F-302 (Smart Recipe Suggestion):** Users can submit a subset of available fridge items to the AI orchestrator to receive recipe recommendations that maximize existing ingredients and identify missing items.
*   **F-303 (Automated Shopping List Aggregation):** The system must compare the ingredients required for the active weekly meal plan against the "available" items in the user's digital fridge, automatically generating a consolidated list of missing ingredients to buy.

### 3.4 AI Orchestration & Guardrails (AI Orchestration Service)
*   **F-401 (Non-Blocking Secret Caching):** The Python worker must retrieve LLM API tokens asynchronously at runtime using Google Cloud Secret Manager with a thread-safe, 300-second Time-To-Live (TTL) cache.
*   **F-402 (Strict Input/Output Schema Enforcement):** LLM outputs must be parsed using a rigid Pydantic schema configured to forbid extra attributes (`extra = "forbid"`), preventing prompt injection exploits.
*   **F-403 (Dead Letter Queue Routing):** If LLM output validation fails, the worker must reject the Pub/Sub message, triggering immediate routing to a Dead Letter Queue (DLQ) for engineering audit, instead of defaulting to empty data.

---

## 4. Non-Functional Constraints

### 4.1 System Security & IAM Model
*   **N-101 (Cryptographically Signed Internal JWTs):** Apigee Gateway must terminate external client sessions, validate OIDC claims, and issue short-lived (15-minute) internal JWTs. Downstream microservices must cryptographically verify these internal tokens' signature, audience (`aud`), and scopes (`scp`) via gRPC interceptors.
*   **N-102 (Zero-Trust Network Policies):** Pod-to-pod communication must enforce mutual TLS (mTLS) through GKE Anthos Service Mesh. GKE NetworkPolicies must isolate the Python AI Worker namespace, blocking all direct access to PostgreSQL and internal Go services.
*   **N-103 (Egress Whitelisting & TLS Origination):** Python AI Worker outbound connections must be routed through an egress proxy (Envoy) configured to enforce SNI verification and TLS origination, strictly limited to secure Vertex AI domains (`*.googleapis.com`).
*   **N-104 (GDPR Compliance via Cryptographic Erasure):** To support the "Right to Be Forgotten" within Cloud Storage backups protected by 365-day WORM locks, the system must perform cryptographic erasure (crypto-shredding) by permanently deleting the user's data encryption key (DEK) from the KMS key directory.

### 4.2 SRE, Scalability, & Performance SLOs
*   **N-201 (Availability SLO):** The platform must maintain $\ge 99.9\%$ successful HTTP/gRPC responses (excluding 4xx client errors) at the Apigee Gateway over any rolling 30-day window.
*   **N-202 (Latency SLO):** $95\%$ of non-AI synchronous database and profile queries must resolve in $< 150\text{ms}$.
*   **N-203 (Fail-Closed Revocation Policy):** If Memorystore for Redis is unavailable, downstream Go services must fail-closed on active session writes and PII reads. Active JWT validation must degrade to a secure local in-memory token cache with short-lived TTL configurations.
*   **N-204 (Damped KEDA Auto-Scaling):** To prevent LLM API rate limit starvation (HTTP 429), KEDA scaling on the GKE Python worker deployment must be capped at 16 maximum replicas, with a 300-second scale-down stabilization window and a damped 50% scale-up step policy.

---

## 5. Implementation Tasklist (Horizontal Phase Execution)

### Phase 1: Security Foundation & Cloud KMS Integration
1. Configure GCP KMS key rings and provision the Key Encryption Keys (KEK) for application-layer envelope encryption.
2. Develop a shared Go cryptographic package to handle AES-256-GCM encryption/decryption of PII fields (`email`, `name`).
3. Implement the dynamic **Versioned Blind Index Pattern** in Go utilizing SHA256 salted HMAC values to enable `O(1)` database email lookups.
4. Set up GCP Secret Manager with a thread-safe, non-blocking TTL cache in Python using `SecretManagerServiceAsyncClient`.
5. Establish Apigee API Gateway JWT signing configurations, creating keys in Google Cloud KMS for generating internal 15-minute tokens.

### Phase 2: Database Schema & Core Go Services (Hexagonal Architecture)
6. Write backward-compatible, transaction-safe PostgreSQL schemas for `users`, `user_goals`, `meal_plans`, and `inventory_items` tables.
7. Configure the Go microservice database pool limits dynamically with safe lifecycle thresholds (`MaxOpenConns=150`, `MaxIdleConns=50`, `ConnMaxLifetime=3m`).
8. Implement the Go dynamic gRPC interceptor enforcing fail-fast initialization checks and validation of signed JWT audience/scopes.
9. Implement a robust circuit breaker pattern (`gobreaker`) within the Go database handler to protect the application during Cloud SQL failover events.
10. Code the Go database migrator container and integrate it as an ArgoCD `PreSync` dry-run hook within the GKE GitOps pipeline.

### Phase 3: Pub/Sub Messaging & Async Python Worker
11. Provision GCP Pub/Sub topics for `Job.Created` and configure the main subscription with a Dead Letter Queue (DLQ) topic targeting 5 delivery attempts.
12. Configure the Pub/Sub subscription retry policies in Terraform with exponential backoff constraints (`minimum_backoff = "10s"`, `maximum_backoff = "600s"`).
13. Develop the Python AI Orchestration worker using asyncio loops, integrating W3C trace-context propagation across Pub/Sub boundaries.
14. Implement rigid Pydantic output schemas (`extra = "forbid"`) within the Python worker to validate LLM payloads.
15. Code exact-type exception sanitization (`MetricsSafety.get_sanitized_label`) in Python to eliminate Prometheus metric cardinality explosion.

### Phase 4: GKE Networking, Egress Guardrails, & Auto-Scaling
16. Author GKE Kubernetes NetworkPolicies to isolate the `python-ai-worker` namespace, blocking PostgreSQL and profile-service ingress/egress.
17. Deploy the GKE `egress-proxy` Envoy container, configuring strict SNI validation, TLS origination, and domain whitelisting to `*.googleapis.com`.
18. Configure GKE Anthos Service Mesh virtual routing rules to enforce mutual TLS (mTLS) for all internal service communication.
19. Define the GKE KEDA auto-scaler (`ScaledObject`) targeting GCP Pub/Sub backlog metrics, capping maximum replicas at 16 with a 50% scale-up step.
20. Create the Argo Rollouts canary deployment configuration, declaring Prometheus error-rate analysis gates for progressive Go service rollouts.

---

# Architecture Blueprint (ARCHITECTURE.md)

## 1. Hexagonal/Clean Architecture System Structure

The system uses a highly structured **Hexagonal (Ports & Adapters) Clean Architecture** pattern to isolate core business logic from database, networking, and cloud provider dependencies.

```
       +-------------------------------------------------------------+
       |                        GKE Pod Boundary                     |
       |                                                             |
       |  +-------------------------------------------------------+  |
       |  |                       ADAPTERS                        |  |
       |  |                                                       |  |
       |  |   gRPC Controllers / PubSub Subs / REST Handlers      |  |
       |  +---------------------------+---------------------------+  |
       |                              | Implements                   |
       |                              v                              |
       |  +---------------------------+---------------------------+  |
       |  |                         PORTS                         |  |
       |  |                                                       |  |
       |  |      Inbound: UserUseCase, PlanUseCase Ports          |  |
       |  +---------------------------+---------------------------+  |
       |                              ^                              |
       |                              | Orchestrates                 |
       |                              v                              |
       |  +---------------------------+---------------------------+  |
       |  |                        DOMAIN                         |  |
       |  |                                                       |  |
       |  |             Core Entity Entities & Rules              |  |
       |  +---------------------------+---------------------------+  |
       |                              ^                              |
       |                              | Leverages                    |
       |                              v                              |
       |  +---------------------------+---------------------------+  |
       |  |                         PORTS                         |  |
       |  |                                                       |  |
       |  |     Outbound: UserRepository, KMS, PubSub Ports       |  |
       |  +---------------------------+---------------------------+  |
       |                              ^                              |
       |                              | Implemented By               |
       |  +---------------------------+---------------------------+  |
       |  |                       ADAPTERS                        |  |
       |  |                                                       |  |
       |  |       PGClient (pgx), CloudKMSClient, PubSub Pub      |  |
       |  +-------------------------------------------------------+  |
       +-------------------------------------------------------------+
```

### 1.1 Directory Layout Matrix (Go Services)
```
/cmd
  /server
    main.go                 # App bootstrapper & Dependency Injection container
/internal
  /domain
    user.go                 # Core user entities, blind index version, & crypt rules
    meal.go                 # Meal plan structural domain matrices
  /ports
    inbound.go              # Port interfaces for controllers driving business logic
    outbound.go             # Port interfaces for database, cache, and KMS adaptors
  /adapters
    /primary
      /grpc                 # gRPC endpoint handlers and middleware interceptors
      /pubsub               # Pub/Sub background message consumers
    /secondary
      /postgres             # PostgreSQL pgx drivers, SQL scripts, & connection pool
      /kms                  # GCP KMS clients managing envelope encryption wrapper
      /redis                # Memorystore Redis connection clients
```

---

## 2. Database Schema Topology

```
+------------------------------------+          +-----------------------------------+
|               users                |          |            user_goals             |
+------------------------------------+          +-----------------------------------+
| PK  | user_id (Identity)           |<-------- | PK, FK | user_id (References)     |
|     | email (Encrypted Cipher)     |          |        | target_calories (Integer) |
|     | email_salt (BYTEA)           |          |        | diet_goal (Enum Check)   |
|     | email_blind_index_version    |          |        | excluded_ingredients     |
|     | email_blind_index (CHAR(64)) |          +-----------------------------------+
|     | name (Encrypted Cipher)      |
+------------------------------------+
                  |
                  | (1 to Many)
                  v
+------------------------------------+          +-----------------------------------+
|             meal_plans             |          |          inventory_items          |
+------------------------------------+          +-----------------------------------+
| PK  | plan_id (UUID)               |          | PK  | item_id (Identity)          |
| FK  | user_id (References)         |          | FK  | user_id (References)        |
|     | plan_date (Date)             |          |     | ingredient_name (Text)      |
|     | meals (JSONB Array Check)    |          |     | status (Enum Check)         |
+------------------------------------+          +-----------------------------------+
```

### 2.1 Complete SQL Declarations (PostgreSQL Specifics)

```sql
-- Enforce UUID generation extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core User Table (PII encrypted, indexed via versioned salted blind indices)
CREATE TABLE users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL,                         -- Application-layer envelope-encrypted ciphertext
    email_salt BYTEA NOT NULL,                   -- Row-specific cryptographic salt
    email_blind_index_version SMALLINT NOT NULL, -- Rotatable pepper schema version tracker
    email_blind_index CHAR(64) NOT NULL,          -- Salted HMAC-SHA256 blind index for O(1) searches
    name TEXT NOT NULL,                          -- Application-layer envelope-encrypted ciphertext
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Compound Index for fast lookup with support for salt/pepper versioning
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

-- Meal Plans Table (JSONB array structure)
CREATE TABLE meal_plans (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    plan_date DATE NOT NULL,
    -- JSONB validation without dynamic string casting to prevent database performance overhead
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
-- Partial index optimized for retrieving low stock / depleted items
CREATE INDEX idx_active_inventory_low_stock 
ON inventory_items (user_id, status) 
WHERE status = 'depleted';
```

---

## 3. Security & IAM Model

```
       +-----------------------------------------------------------------+
       |                        GKE VPC Boundary                         |
       |                                                                 |
       |  +------------------+                   +--------------------+  |
       |  |   DMZ Namespace  |                   |  App Mesh Namespace|  |
       |  |                  |                   |                    |  |
       |  | [Apigee Gateway] |                   | [Go Microservices] |  |
       |  +--------+---------+                   +---------+----------+  |
       |           |                                       |             |
       |           | Internal JWT Context                  | mTLS        |
       |           v (mTLS via ASM)                        v             |
       |  +-----------------------------------------------------------+  |
       |  |  Secure Isolated Database Namespace                       |  |
       |  |  [Cloud SQL PostgreSQL]        [Memorystore Redis Cluster]|  |
       |  +-----------------------------------------------------------+  |
       |                                                                 |
       |  +-----------------------------------------------------------+  |
       |  |  High-Risk AI Sandbox Namespace                           |  |
       |  |  [AI Orchestration Svc] ---> [Egress Proxy] --> Vertex AI |  |
       |  +-----------------------------------------------------------+  |
       +-----------------------------------------------------------------+
```

### 3.1 GKE NetworkPolicies
The network security configuration restricts ingress/egress patterns at the GKE boundary, blocking high-risk execution namespaces from standard relational storage access.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ai-worker-isolation-policy
  namespace: mealplanner
spec:
  podSelector:
    matchLabels:
      app: python-ai-worker
  policyTypes:
  - Ingress
  - Egress
  ingress: [] # Blocks all direct incoming requests (no ingress allowed)
  egress:
  - to: # Allow connection to DNS (Kube-DNS)
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
  - to: # Limit HTTP egress strictly to Egress Proxy Pod
    - podSelector:
        matchLabels:
          app: egress-proxy
    ports:
    - protocol: TCP
      port: 443
```

---

## 4. SRE & Observability SLOs

To measure system performance and guarantee operational standards under stress, we define key service indicators and corresponding alert targets.

| Service Border | Service Level Indicator (SLI) | Target SLO | Warning Alert Target |
| :--- | :--- | :--- | :--- |
| **Edge Gateway** | Proportion of HTTP responses resolving to `2xx`/`OK` (excluding 4xx errors) over 30 days. | $\ge 99.9\%$ Availability | $< 99.95\%$ over a 12-hour period |
| **API Endpoints** | Latency of standard database write and profile sync requests. | $95\%$ of requests completed in $< 150\text{ms}$ | P95 latency $> 200\text{ms}$ over 5 minutes |
| **Pub/Sub Sub** | Messages successfully consumed and processed by the AI pipeline. | $\ge 99.5\%$ Success | $> 1\%$ message rejection rate over 1 hour |
| **AI Orchestration** | Processing backlog size (measured via GKE KEDA metric queue depth). | Queue length $< 100$ items for $\ge 99\%$ of a 24h window | Queue backlog $> 500$ messages over 10 minutes |

---

## 5. API Contracts & Proto Interfaces

### 5.1 Protocol Buffer Definition (`meal_planner.proto`)

```protobuf
syntax = "proto3";

package mealplanner.v1;

option go_package = "github.com/mealplanner/api/v1;v1";

service MealPlannerService {
  // Initiates dynamic weekly meal plan creation. Internal token context is checked downstream.
  rpc GenerateWeeklyMealPlan (GenerateWeeklyMealPlanRequest) returns (GenerateWeeklyMealPlanResponse);
  
  // Queries recipes based on available ingredients in the user's digital fridge.
  rpc GetFridgeSuggestions (GetFridgeSuggestionsRequest) returns (GetFridgeSuggestionsResponse);
}

message GenerateWeeklyMealPlanRequest {
  string correlation_id = 1; // Explicit trace context propagated across boundaries
}

message GenerateWeeklyMealPlanResponse {
  string job_id = 1;
  string status = 2; // "queued", "processing", "completed"
  int64 estimated_duration_ms = 3;
}

message GetFridgeSuggestionsRequest {
  string correlation_id = 1;
  repeated string current_fridge_items = 2;
}

message RecipeSuggestion {
  string recipe_id = 1;
  string recipe_title = 2;
  repeated string matching_ingredients = 3;
  repeated string missing_ingredients_to_buy = 4;
  int32 prep_time_minutes = 5;
}

message GetFridgeSuggestionsResponse {
  repeated RecipeSuggestion suggestions = 1;
}
```