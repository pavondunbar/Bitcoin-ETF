# Bitcoin ETF Lifecycle Simulator

<img width="1616" height="973" alt="f35ecc1f-ec4d-459f-a8f2-7096208b5853" src="https://github.com/user-attachments/assets/0367c8fa-8be6-47c1-8cd9-a8f82ad45ff1" />

> **SANDBOX / EDUCATIONAL USE ONLY — NOT FOR PRODUCTION**
>
> This codebase is a reference implementation designed for learning, prototyping, and architectural exploration of Bitcoin ETF systems. It is **not audited, not legally reviewed, and must not be used to manage real Bitcoin, issue real ETF shares, or interface with real exchanges and custody providers.** See the [Production Warning](#production-warning) section for full details.

Enterprise-grade Bitcoin ETF lifecycle platform with real-time NAV calculation, deterministic settlement, MPC-based transaction signing, and institutional-grade custody. Models institutional fund structures like iShares, Grayscale, and Blackrock Bitcoin ETFs.

The system implements:

- Blockchain-grade **double-entry ledger accounting** (append-only, immutable, balance-derived)
- **Deterministic settlement state machine** (PENDING → APPROVED → SIGNED → BROADCASTED → CONFIRMED)
- **MPC 2-of-3 quorum transaction signing** with simulated blockchain broadcast and confirmation
- **Transactional outbox event publishing** with dead letter queue and retry backoff
- **Role-based access control** with separation of duties across 6 roles
- **Comprehensive audit trails** with request_id, trace_id, and actor metadata on every state transition
- **Reconciliation engine** that replays the ledger, recomputes balances, and alerts on mismatch
- **Deterministic state rebuild** — full system state can be reconstructed from the ledger alone
- **Trust-boundary network model** with only the API gateway exposed to the internet

---

## Table of Contents

* [Quick Start](#quick-start)
* [Architecture](#architecture)
* [Settlement State Machine](#settlement-state-machine)
* [Services](#services)
* [Data Model](#data-model)
* [Kafka Topics](#kafka-topics)
* [API Reference](#api-reference)
* [Getting Started](#getting-started)
* [Monitoring](#monitoring)
* [Scripts and Utilities](#scripts-and-utilities)
* [Technical Design](#technical-design)
* [Production Warning](#production-warning)
* [License](#license)

---

## Quick Start

```bash
# Clone and configure
git clone https://github.com/pavondunbar/Bitcoin-ETF.git
cd Bitcoin-ETF
cp .env.example .env

# Build and start the platform
make build
make up

# Run a full ETF lifecycle demo
make demo

# Run reconciliation
make reconcile

# Rebuild state from ledger
make rebuild

# Check health
curl http://localhost:8000/health

# View logs
make logs
```

---

## Architecture

```
                            Internet
                               |
                     +---------+---------+
                     |   API Gateway     |  :8000 (only exposed port)
                     |  RBAC + audit     |
                     +----+-+-+-+--------+
                          | | | |
           DMZ network     | | | | internal network
      +--------------------+ | | +--------------------+
      |             +--------+ +--------+              |
      v             v                   v              v
+----------+  +----------+  +----------+  +----------+
| ETF      |  | Bitcoin  |  | NAV      |  | Execution|
| Issuer   |  | Custody  |  | Engine   |  | Engine   |
| :8001    |  | :8002    |  | :8003    |  | :8004    |
+----------+  +----------+  +----------+  +----------+
      |             |             |            |
      +-----+-------+-----+-------+            |
            |             |                    |
      +-----+---+   +-----+----+        +------+-------+
      |Postgres  |   | Kafka    |        |  Bitcoin     |
      | :5432    |   | :9092    |        |  Network     |
      +---------+   +----------+        | (simulated)  |
                          |             +------+-------+
              +-----------+---+                |
              |       |       |                |
        +-----+--+ +--+----+ +---+------+ +---+-------+
        |Complian-| |Outbox | |Reconcili-| | Price Feed|
        |ce Mon.  | |Publish| |ation Eng.| | Oracle    |
        | :8009   | | :8010 | |          | | :8008     |
        +---------+ +-------+ +----------+ +-----------+

                   signing network (isolated)
              +------+------+------+------+
              |  MPC Gateway  :8010       |
              +--+-------+-------+--------+
                 |       |       |
              +--+--+ +--+--+ +--+--+
              |node1| |node2| |node3|
              +-----+ +-----+ +-----+
              (2-of-3 quorum signing)
```

### Network Isolation

| Network | Services | Internet Access |
| --- | --- | --- |
| **dmz** | api-gateway, prometheus, grafana | Yes (host-reachable) |
| **internal** | All microservices, postgres, kafka, zookeeper, outbox-publisher, reconciliation-engine | No |
| **signing** | mpc-gateway, mpc-node-1, mpc-node-2, mpc-node-3 | No (isolated trust domain) |

The API gateway bridges dmz and internal networks. The MPC signing zone is fully isolated — only the settlement engine can reach it through the signing network. All other backend services operate in the internal network with no external connectivity.

### Infrastructure

| Component | Image | Purpose |
| --- | --- | --- |
| PostgreSQL | `postgres:16` | Persistent storage, immutable double-entry ledger |
| Kafka | `confluentinc/cp-kafka:7.5.0` | Event streaming between services |
| Zookeeper | `confluentinc/cp-zookeeper:7.5.0` | Kafka coordination |
| Prometheus | `prom/prometheus` | Metrics collection |
| Grafana | `grafana/grafana` | Dashboards and visualization |

---

## Settlement State Machine

Every settlement follows a deterministic 5-step state machine. Each transition is validated, persisted to the database, and recorded in an immutable audit log.

```
PENDING ──→ APPROVED ──→ SIGNED ──→ BROADCASTED ──→ CONFIRMED
   |            |           |            |              |
   |            |           |            |              |
 Create     Compliance   MPC 2-of-3   Blockchain     6 block
 settlement  & risk      quorum       tx broadcast   confirmations
 instruction check       signing      (simulated)    (finality)
```

### State Descriptions

| State | Actor | Action |
| --- | --- | --- |
| **PENDING** | system | Settlement instruction created from netting result |
| **APPROVED** | approver | Compliance and risk checks passed |
| **SIGNED** | signer | MPC 2-of-3 quorum produces combined signature |
| **BROADCASTED** | system | Signed transaction broadcast to blockchain (simulated: SHA-256 tx hash, incrementing block number) |
| **CONFIRMED** | system | 6 block confirmations received (Bitcoin finality threshold) |

### Blockchain Rails

Transaction broadcast and confirmation are simulated for demo purposes:

- **Transaction hashes**: Deterministic SHA-256 hashes formatted as `0x` + 64 hex characters
- **Block numbers**: Incrementing from a base of 850,000 (approximate Bitcoin block height)
- **Confirmations**: 6 blocks (standard Bitcoin finality)
- **Network**: `bitcoin-mainnet-simulated`

In production, replace `services/blockchain.py` with Web3.py or bitcoinlib RPC calls.

### MPC 2-of-3 Quorum Signing

The signing zone contains 3 isolated MPC nodes. Any 2 must participate to produce a valid combined signature.

1. Settlement handler creates a signing payload (SHA-256 of settlement_id + amount)
2. 2 of 3 nodes are randomly selected to form a quorum
3. Each node produces a partial signature using its node-specific key material
4. The MPC gateway combines partial signatures into a single composite signature
5. The combined signature is stored on the settlement instruction and used for broadcast

Node keys and signing logic are simulated. In production, replace with a threshold ECDSA library (e.g., Fireblocks MPC, Lit Protocol).

---

## Services

### API Gateway (port 8000)

The sole internet-facing service. Implements full RBAC with separation of duties.

**Authentication**: SHA-256 hashed API keys stored in `api_keys` table. Every request must include an `X-API-Key` header.

**Authorization**: Role-permission matrix stored in `role_permissions` table. Each endpoint maps to a (resource, action) pair checked against the caller's role.

**Audit trail**: Every request is logged to the `audit_trail` Kafka topic with `request_id`, `trace_id`, actor identity, role, method, path, status code, and timestamp.

**RBAC Roles:**

| Role | Permissions |
| --- | --- |
| `admin` | Full access to all resources and actions |
| `approver` | Approve settlements and withdrawals, read trades and ledger |
| `trader` | Submit trades, read trades and ledger |
| `auditor` | Read-only access to all resources |
| `signer` | Sign settlements, read settlement status |
| `system` | Publish events, internal operations, create settlements |

**Routes:**

| Path | Method | Resource | Action |
| --- | --- | --- | --- |
| `/v1/etf/creation` | POST | trade | create |
| `/v1/etf/redemption` | POST | trade | create |
| `/v1/settlement/approve` | POST | settlement | approve |
| `/v1/settlement/sign` | POST | settlement | sign |
| `/v1/settlement/status` | GET | settlement | read |
| `/v1/ledger/balances` | GET | ledger | read |
| `/v1/ledger/entries` | GET | ledger | read |
| `/health` | GET | (public) | (none) |

### ETF Issuer (port 8001)

Manages the complete lifecycle of Bitcoin ETF share creation, redemption, and tracking. Implements institutional fund accounting with per-share NAV tracking and in-kind redemption workflows.

* Validates KYC/AML status before issuance
* Supports idempotency keys to prevent duplicate processing
* 8-decimal-place precision for share tracking
* Creates matching debit/credit journal entries for all operations
* Publishes events via transactional outbox pattern
* Tracks per-share NAV to prevent dilution
* Manages creation basket composition (Bitcoin units per share creation)

### Bitcoin Custody (port 8002)

Manages secure custody of Bitcoin holdings with multi-signature controls and custody account segregation.

* Maintains segregated custody accounts for each participant
* Tracks Bitcoin UTXO composition and dust amounts
* Advisory locks on custody accounts during transfers
* Row-level locking for atomic balance updates
* Supports hot wallet and cold storage segregation

### NAV Engine (port 8003)

Real-time Net Asset Value calculation using live Bitcoin price feeds.

* Consumes price updates from oracle every 10 seconds
* Calculates per-share NAV with 4-decimal precision
* Accrues management fees and performance fees daily
* Tracks cash drag from redemption proceeds
* Publishes NAV updates for exchange data feeds

### Execution Engine (port 8004)

Manages Bitcoin trading operations, rebalancing, and order execution.

* Executes creation basket trades on multiple venues
* Supports limit orders, market orders, and OTC trades
* Tracks execution quality metrics (VWAP, slippage)
* Supports multiple settlement methods (on-chain, exchange custody)

### Price Feed Oracle (port 8008)

Aggregates Bitcoin prices from multiple sources and publishes canonical price for NAV calculation and compliance.

* Applies median filtering to detect outliers
* Publishes canonical price every 10 seconds to Kafka
* Implements price staleness monitoring
* Supports fallback to previous close on data gaps
* Logs all price moves > 2% for compliance

### Compliance Monitor (port 8009)

Consumes ETF operations from Kafka and runs rule-based AML screening.

| Rule | Threshold |
| --- | --- |
| Large creation (suspicious source) | >= $250,000 fiat in single creation |
| Velocity limit | > 20 creations per participant per hour |
| Structuring detection | Multiple creations < $10,000 each within 1 day |
| Redemption to high-risk address | Destination address flagged in Chainalysis/Elliptic |
| Concentration risk | Single participant > 5% of fund |

### Outbox Publisher

Polls the `outbox` table for PENDING events and relays them to Kafka.

* Uses `FOR UPDATE SKIP LOCKED` for safe horizontal scaling
* Retry limit: 5 attempts with exponential backoff (2^n seconds)
* Failed messages routed to `dlq_default` Kafka topic after retries exhausted
* Outbox status tracks: PENDING → SENT or PENDING → FAILED → DLQ

### Reconciliation Engine

Verifies ledger integrity by replaying all journal entries and comparing derived balances.

1. **Replay**: Reads all `journal_entries`, computes `SUM(debit) - SUM(credit)` per account
2. **Compare**: Reads `account_balances` view (the derived read model)
3. **Alert**: Records results to `reconciliation_results` table, flags mismatches
4. **Invariant check**: Verifies global debit/credit balance (total debits must equal total credits)

Run with `make reconcile`.

### MPC Signing Gateway (port 8010)

Coordinates the 2-of-3 MPC signing quorum.

* Receives signing requests from the settlement engine
* Collects partial signatures from 2 of 3 MPC nodes
* Combines partial signatures into a single composite signature
* Runs on the isolated `signing` network

### MPC Nodes (3 instances)

Each node holds independent key material and produces partial signatures.

* Isolated on the `signing` network (no internet, no access to other services)
* Each node identified by `NODE_ID` environment variable
* Partial signatures are HMAC-SHA256 based (simulated for demo)

---

## Data Model

### Core Ledger Tables

```
journal_entries (IMMUTABLE — triggers prevent UPDATE/DELETE)
  +- id UUID PK
  +- account TEXT
  +- debit NUMERIC (mutually exclusive with credit)
  +- credit NUMERIC (mutually exclusive with debit)
  +- request_id TEXT          ← audit trail
  +- trace_id TEXT            ← audit trail
  +- actor TEXT               ← audit trail
  +- created_at TIMESTAMPTZ

event_log (IMMUTABLE — triggers prevent UPDATE/DELETE)
  +- id UUID PK
  +- event_type TEXT
  +- payload JSONB
  +- idempotency_key TEXT UNIQUE
  +- request_id TEXT          ← audit trail
  +- trace_id TEXT            ← audit trail
  +- actor TEXT               ← audit trail
  +- created_at TIMESTAMPTZ

account_balances (VIEW — derived, not stored)
  SELECT account, SUM(debit - credit) AS balance
  FROM journal_entries GROUP BY account
```

### Settlement Tables

```
settlement_instructions
  +- id UUID PK
  +- event_id UUID
  +- event_type TEXT
  +- counterparty TEXT
  +- amount NUMERIC
  +- currency TEXT (default: USD)
  +- status TEXT               ← PENDING|APPROVED|SIGNED|BROADCASTED|CONFIRMED
  +- mpc_signature TEXT        ← combined MPC signature
  +- signer_quorum JSONB       ← signing node details
  +- tx_hash TEXT              ← blockchain transaction hash (0x...)
  +- block_number BIGINT       ← blockchain block number
  +- confirmations INT         ← block confirmation count
  +- request_id TEXT           ← audit trail
  +- trace_id TEXT             ← audit trail
  +- actor TEXT                ← audit trail
  +- created_at TIMESTAMPTZ
  +- approved_at TIMESTAMPTZ
  +- signed_at TIMESTAMPTZ
  +- broadcasted_at TIMESTAMPTZ
  +- confirmed_at TIMESTAMPTZ

settlement_state_history (IMMUTABLE)
  +- id UUID PK
  +- settlement_id UUID FK
  +- previous_status TEXT
  +- new_status TEXT
  +- actor TEXT
  +- reason TEXT
  +- metadata JSONB            ← MPC signatures, tx details, etc.
  +- created_at TIMESTAMPTZ
```

### Event Delivery Tables

```
outbox
  +- id UUID PK
  +- event_id UUID
  +- event_type TEXT
  +- payload JSONB
  +- status TEXT               ← PENDING|SENT|FAILED|DLQ
  +- retry_count INT (default: 0)
  +- max_retries INT (default: 5)
  +- last_error TEXT
  +- created_at TIMESTAMPTZ
  +- sent_at TIMESTAMPTZ
```

### RBAC Tables

```
api_keys
  +- id UUID PK
  +- key_hash TEXT UNIQUE      ← SHA-256 of raw API key
  +- name TEXT
  +- role TEXT                 ← admin|approver|trader|auditor|signer|system
  +- is_active BOOLEAN
  +- created_at TIMESTAMPTZ

role_permissions
  +- id UUID PK
  +- role TEXT
  +- resource TEXT             ← trade|settlement|ledger|event|withdrawal|*
  +- action TEXT               ← create|read|approve|sign|publish|*
  +- UNIQUE(role, resource, action)
```

### Reconciliation Tables

```
reconciliation_results (IMMUTABLE)
  +- id UUID PK
  +- run_id UUID               ← groups results from a single run
  +- account TEXT
  +- expected_balance NUMERIC
  +- actual_balance NUMERIC
  +- difference NUMERIC
  +- status TEXT               ← MATCH|MISMATCH|ERROR
  +- created_at TIMESTAMPTZ
```

### Other Tables

```
settlement_instructions        (CCP/RTGS layer — see above)
fx_exposures                   (multi-currency extension)
```

---

## Kafka Topics

Topics provisioned at startup via `make kafka-init`:

| Topic | Purpose |
| --- | --- |
| `trades` | Trade creation requests |
| `event_log` | Primary event stream (outbox relay target) |
| `creation_requests` | ETF share creation orders |
| `settlement_commands` | Settlement approval and signing commands |
| `audit_trail` | Immutable request audit log (request_id, actor, role, path, status) |
| `dlq_default` | Dead letter queue for messages that failed after max retries |

---

## API Reference

All requests go through the API gateway at `http://localhost:8000`. Include the API key as `X-API-Key` header.

### Authentication

```bash
# Every request (except /health) requires an API key
curl http://localhost:8000/v1/ledger/balances \
  -H "X-API-Key: $API_KEY"

# Optional: pass trace context
curl http://localhost:8000/v1/ledger/balances \
  -H "X-API-Key: $API_KEY" \
  -H "X-Request-ID: req-001" \
  -H "X-Trace-ID: trace-abc"
```

### ETF Creation

```bash
# Submit creation order (in-kind: send Bitcoin, receive shares)
curl -X POST http://localhost:8000/v1/etf/creation \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": "<participant-uuid>",
    "bitcoin_amount": "10.5",
    "idempotency_key": "CREATE-20240615-001"
  }'
```

### Settlement Operations

```bash
# Approve a settlement (requires approver role)
curl -X POST http://localhost:8000/v1/settlement/approve \
  -H "X-API-Key: $APPROVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "settlement_id": "<settlement-uuid>"
  }'

# Sign a settlement (requires signer role)
curl -X POST http://localhost:8000/v1/settlement/sign \
  -H "X-API-Key: $SIGNER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "settlement_id": "<settlement-uuid>"
  }'

# View settlement status and blockchain details
curl http://localhost:8000/v1/settlement/status \
  -H "X-API-Key: $API_KEY"
```

### Ledger Queries

```bash
# Get derived account balances
curl http://localhost:8000/v1/ledger/balances \
  -H "X-API-Key: $API_KEY"

# Get journal entries with audit trail
curl "http://localhost:8000/v1/ledger/entries?limit=50" \
  -H "X-API-Key: $API_KEY"
```

### Health

```bash
# Gateway health (public, no auth required)
curl http://localhost:8000/health
```

---

## Getting Started

### Prerequisites

* Docker and Docker Compose
* Python 3.11+ (for running the demo locally)
* 2 GB RAM minimum (Kafka + PostgreSQL + services)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set values:

```bash
POSTGRES_PASSWORD=<strong-password>
GATEWAY_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
GRAFANA_PASSWORD=<grafana-password>
```

### 2. Start the platform

```bash
make build
make up
```

This starts the following containers:

1. **postgres** — database with schema, triggers, and RBAC seed data
2. **zookeeper** — Kafka coordination
3. **kafka** — event broker
4. **api-gateway** — RBAC auth, audit logging, reverse proxy
5. **trade-ingestion** — trade processing
6. **netting-engine** — netting calculations
7. **settlement-engine** — deterministic settlement state machine
8. **execution-engine** (margin-engine) — trade execution
9. **collateral-manager** — custody management
10. **liquidation-engine** — emergency liquidation
11. **price-oracle** — Bitcoin price feeds
12. **compliance-monitor** — AML/regulatory screening
13. **outbox-publisher** — event relay to Kafka with DLQ
14. **reconciliation-engine** — ledger integrity verification
15. **signing-gateway** — MPC signing coordinator
16. **mpc-node-1, mpc-node-2, mpc-node-3** — isolated signing nodes
17. **prometheus** + **grafana** — observability

### 3. Verify

```bash
# Check containers running
docker compose ps

# Test gateway health
curl http://localhost:8000/health

# Expected: {"status": "ok", "db": "ok"}
```

### 4. Run the demo

```bash
make demo
```

The demo executes 3 full trade cycles. Each cycle runs through:

1. **Trade creation** — authorized participant submits basket
2. **Trade ingestion** — enriches trade context, propagates trace_id
3. **Netting** — calculates net quantities
4. **Settlement** — walks through all 5 states:
   - PENDING → APPROVED → SIGNED (MPC 2-of-3) → BROADCASTED (simulated tx hash) → CONFIRMED (6 blocks)
5. **Custody update** — records finality
6. **Ledger posting** — double-entry journal writes with audit context

After all cycles:

7. **Reconciliation** — replays ledger, verifies debit/credit balance, checks all accounts
8. **State rebuild** — reconstructs full system state from the event log

### 5. Post-demo verification

```bash
# Run reconciliation independently
make reconcile

# Rebuild state from ledger
make rebuild

# Inspect ledger
make db-ledger

# Inspect balances
make db-balances

# Inspect settlements
make db-rtgs
```

### Teardown

```bash
make down        # Stop but keep volumes
make clean       # Stop and remove volumes (full reset)
```

---

## Monitoring

| Service | URL | Credentials |
| --- | --- | --- |
| Prometheus | <http://localhost:9090> | None |
| Grafana | <http://localhost:3000> | admin / `$GRAFANA_PASSWORD` |

Each microservice exposes a `/metrics` endpoint scraped by Prometheus.

---

## Scripts and Utilities

| Script | Purpose |
| --- | --- |
| `run_demo.py` | Full lifecycle demo: 3 trade cycles + reconciliation + state rebuild |
| `scripts/migrate.py` | Schema migrations (adds audit columns, settlement state, RBAC tables) |
| `scripts/demo.py` | End-to-end demo: onboarding, creation, redemption, trading |
| `scripts/load_test.py` | Concurrent creation/redemption load testing |
| `scripts/fund_integrity.py` | Fund accounting audit |
| `scripts/kafka_tail.py` | Real-time Kafka topic monitoring |

### Makefile Targets

```bash
make help              # Show all targets
make build             # Build all images
make up                # Start all containers
make down              # Stop containers
make clean             # Stop and remove volumes (full reset)
make demo              # Run full ETF lifecycle demo
make reconcile         # Run reconciliation engine
make rebuild           # Deterministic state rebuild from ledger
make migrate           # Run database migrations
make kafka-init        # Create Kafka topics (trades, event_log, audit_trail, dlq_default, etc.)
make logs              # Follow all service logs
make ps                # Show container status
make health            # Check system health
make test              # Run test suite
make integrity         # Ledger replay + invariants
make db-ledger         # Inspect journal entries
make db-balances       # Show derived account balances
make db-rtgs           # Show settlement instructions
make db-fx             # Show FX exposures
make shell-pg          # PostgreSQL shell
make shell-kafka       # Kafka shell
make topics            # List Kafka topics
make open-docs         # Open API docs
```

---

## Technical Design

### Trade and Settlement Lifecycle

A single trade flows through the following event pipeline:

```
TradeCreated
  → BasketRequested         (trade ingestion enriches context)
    → NettingExecuted        (netting calculates net quantities)
      → SettlementPending    (settlement instruction created in DB)
        → SettlementApproved (compliance/risk check passed)
          → SettlementSigned (MPC 2-of-3 quorum signing)
            → SettlementBroadcasted (tx submitted to blockchain)
              → SettlementConfirmed (6 block confirmations)
                → CustodyUpdated (finality recorded)
```

Every event carries `trace_id` inherited from the root trade event, enabling full trace reconstruction across the entire lifecycle.

### Audit Trail Architecture

Every state transition records three identifiers:

| Field | Purpose |
| --- | --- |
| `request_id` | Unique per API request. Ties all downstream events to the originating HTTP call. |
| `trace_id` | Unique per trade lifecycle. Propagated via `Event.child()` so all events in a trade share the same trace. |
| `actor` | Identity of the entity that triggered the transition (e.g., `demo-ap`, `approver`, `signer`, `system`). |

These fields are stored on:
- `event_log` (every domain event)
- `journal_entries` (every ledger write)
- `settlement_instructions` (every settlement)
- `settlement_state_history` (every state transition)
- `audit_trail` Kafka topic (every API request)

### Double-Entry Ledger

Every fund operation creates debit and credit journal entries with audit context:

```sql
-- Example: settlement confirmed
INSERT INTO journal_entries (id, account, debit, credit, request_id, trace_id, actor)
VALUES (uuid, 'clearing.cash_obligation', 65000000, NULL, 'req-001', 'trace-abc', 'system');

INSERT INTO journal_entries (id, account, debit, credit, request_id, trace_id, actor)
VALUES (uuid, 'clearing.etf_inventory', NULL, 65000000, 'req-001', 'trace-abc', 'system');
```

**Invariant**: `SUM(all debits) = SUM(all credits)` globally. The reconciliation engine verifies this.

**Balances are never stored** — they are always derived:

```sql
CREATE VIEW account_balances AS
SELECT account, SUM(COALESCE(debit, 0) - COALESCE(credit, 0)) AS balance
FROM journal_entries GROUP BY account;
```

### Immutability Enforcement

Database triggers prevent UPDATE and DELETE on critical tables:

| Table | Protection |
| --- | --- |
| `journal_entries` | Fully immutable (no UPDATE, no DELETE) |
| `event_log` | Fully immutable |
| `settlement_state_history` | Fully immutable |
| `reconciliation_results` | Fully immutable |

### Transactional Outbox Pattern

Business operations and event publishing happen in a single database transaction:

1. Service publishes event via `EventBus.publish()`
2. `persist_event()` atomically writes to both `event_log` and `outbox` in one transaction
3. If duplicate (idempotency_key conflict) → short-circuit, no outbox write
4. `outbox_worker` polls PENDING events with `FOR UPDATE SKIP LOCKED`
5. Publishes to Kafka, marks as SENT
6. On failure: increments `retry_count`, applies exponential backoff (2^n seconds)
7. After 5 retries: moves to DLQ status, publishes to `dlq_default` Kafka topic

### Dead Letter Queue

Messages that fail after max retries (default: 5) are:

1. Marked as `DLQ` status in the `outbox` table
2. Published to the `dlq_default` Kafka topic with full context:
   - Original `outbox_id`, `event_type`, `payload`
   - `retry_count` and `last_error`
3. Available for manual inspection and replay

### Role-Based Access Control

RBAC is enforced at the API gateway level:

1. **Authenticate**: `X-API-Key` header → SHA-256 hash → lookup in `api_keys` table
2. **Authorize**: Endpoint maps to (resource, action) → checked against `role_permissions` table
3. **Audit**: Every request logged to `audit_trail` Kafka topic with actor, role, path, status

Permissions support wildcards (`*`) for both resource and action, enabling admin-level access.

### Reconciliation

The reconciliation engine verifies two invariants:

1. **Per-account**: Replayed balance (from raw entries) matches the `account_balances` view
2. **Global**: Total debits equal total credits across all accounts

Results are persisted to `reconciliation_results` (immutable) for audit purposes.

### Deterministic State Rebuild

The system can reconstruct its full state from the append-only ledger:

1. `replay(bus)` — reads all events from `event_log` in chronological order and re-publishes them through the event bus. Idempotency keys prevent duplicate processing.
2. `rebuild_state()` — recomputes account balances, event counts, and settlement states purely from database queries. Returns a complete state snapshot without modifying any data.

Run `make rebuild` to verify.

### Concurrency Control

* **Advisory locks**: `pg_advisory_xact_lock` on account+currency prevents double-spend
* **Row-level locking**: `SELECT FOR UPDATE` on custody accounts
* **Optimistic locking**: Version column on `etf_fund_state` prevents conflicting updates
* **Skip-locked queues**: Outbox worker uses `FOR UPDATE SKIP LOCKED` for multi-worker safety
* **Idempotency**: `ON CONFLICT (idempotency_key) DO NOTHING` prevents duplicate events

---

## Project Structure

```
Bitcoin-ETF/
+-- docker-compose.yml          # 20+ containers with 3 trust-boundary networks
+-- Makefile                    # Orchestration (build, demo, reconcile, rebuild, etc.)
+-- .env.example
+-- LICENSE
+-- README.md
+-- run_demo.py                 # Full lifecycle demo with reconciliation + state rebuild
+-- core/
|   +-- bootstrap.py            # Event handler wiring
|   +-- db.py                   # PostgreSQL connection, ledger writes with audit context
|   +-- event_bus.py            # In-process event dispatcher (idempotent + outbox safe)
|   +-- event_store.py          # Atomic event_log + outbox write with audit columns
|   +-- kafka_producer.py       # Kafka client + DLQ publish function
|   +-- outbox_worker.py        # Polling worker with retry backoff and DLQ routing
|   +-- replay.py               # Deterministic replay + full state rebuild from ledger
|   +-- workflow.py             # Event handler stubs
+-- events/
|   +-- events.py               # Event class with audit context + child() propagation
|   +-- state_machine.py        # Trade + settlement transition rules with validation
+-- services/
|   +-- api/app.py              # API gateway with RBAC middleware + audit logging
|   +-- trade_ingestion.py      # Trade processing with trace propagation
|   +-- netting.py              # Netting engine with trace propagation
|   +-- settlement.py           # 5-step settlement state machine + MPC + blockchain
|   +-- custody.py              # Custody finality with trace propagation
|   +-- ledger_posting.py       # Double-entry journal writes with audit context
|   +-- mpc_signing.py          # 2-of-3 MPC quorum signing (simulated)
|   +-- blockchain.py           # Simulated blockchain broadcast + confirmation
|   +-- mpc-gateway/main.py     # MPC signing gateway (FastAPI)
|   +-- mpc-node/main.py        # MPC signing node (FastAPI)
|   +-- settlement/main.py      # On-chain + fiat settlement functions
|   +-- reconciliation/main.py  # Reconciliation engine (replay → compare → alert)
|   +-- api-gateway/            # Dockerfile
|   +-- compliance-monitor/     # Dockerfile + AML screening
|   +-- custody/                # Dockerfile
|   +-- etf_issuer/             # Dockerfile
|   +-- execution/              # Dockerfile
|   +-- ingestion/              # Dockerfile
|   +-- liquidation/            # Dockerfile
|   +-- nav/                    # Dockerfile
|   +-- nav-engine/             # Dockerfile
|   +-- outbox/                 # Dockerfile
|   +-- reconciliation/         # Dockerfile + main.py
+-- db/
|   +-- schema.sql              # Full schema: ledger, events, outbox, settlements, RBAC, reconciliation
|   +-- triggers.sql            # Immutability triggers for journal_entries, event_log, settlement_state_history, reconciliation_results
+-- scripts/
|   +-- migrate.py              # Schema migrations (audit columns, settlement state, RBAC tables, DLQ columns)
|   +-- demo.py                 # End-to-end lifecycle demo
|   +-- load_test.py            # Concurrent load testing
|   +-- fund_integrity.py       # Fund accounting audit
|   +-- kafka_tail.py           # Real-time topic monitoring
+-- shared/
|   +-- shared/idempotency.py   # Idempotency check/store helpers
+-- workers/
|   +-- outbox_publisher.py     # Async outbox polling worker
+-- monitoring/
|   +-- prometheus.yml          # Prometheus configuration
```

---

## Production Warning

**This project is explicitly NOT suitable for production use.** Bitcoin ETF operations are among the most regulated, operationally complex, and legally sensitive activities in financial services. The following critical components are absent or stubbed:

| Missing Component | Risk if Absent |
| --- | --- |
| Real Bitcoin custody license (Coinbase, Fidelity, Bakkt) | Cannot legally hold institutional Bitcoin |
| Real BTC/USD price feeds (Bloomberg, Reuters, LSEG) | Inaccurate fund valuations |
| Real trade execution with venues (Coinbase Prime, Kraken) | No actual Bitcoin trading |
| SEC fund registration and prospectus | Illegal unregistered fund |
| Real KYC/AML provider integration (Onfido, Chainalysis) | No identity verification or sanctions screening |
| Real MPC cryptography (threshold ECDSA, Shamir's Secret Sharing) | Simulated signing, not cryptographically secure |
| Real blockchain RPC integration (Web3.py, bitcoinlib) | Simulated transaction hashes and block numbers |
| Regulatory reporting (Form 13F, daily NAV publication) | SEC violations |
| Hardware wallet / HSM key storage | No cryptographic key security |
| Fund accounting audit (Big 4 audit firm) | Unaudited financial statements |
| Insurance (crime, custody liability) | No coverage for Bitcoin loss |
| Catastrophe recovery procedures | No tested failover for fund operations |
| TLS/mTLS between services | Unencrypted inter-service communication |

> Bitcoin ETFs at institutional scale require: SEC registration, real custody partnerships, real exchange memberships, regulatory approval from relevant authorities (SEC, CFTC), KYC/AML infrastructure, and legal agreements with all participants. **Do not use this code to issue, manage, or trade any real Bitcoin or launch an actual ETF fund.**

---

## License

This project is provided as-is for educational and reference purposes under the MIT License.

---

*Built with ♥️ by Pavon Dunbar — Modeled on institutional Bitcoin ETF systems (iShares IBIT, Grayscale GBTC, Blackrock GBTC)*
