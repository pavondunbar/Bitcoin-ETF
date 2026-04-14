# Bitcoin ETF Lifecycle Simulator

> ⚠️ **SANDBOX / EDUCATIONAL USE ONLY — NOT FOR PRODUCTION**
> 
> This codebase is a reference implementation designed for learning, prototyping, and architectural exploration of Bitcoin ETF systems. It is **not audited, not legally reviewed, and must not be used to manage real Bitcoin, issue real ETF shares, or interface with real exchanges and custody providers.** See the [Production Warning](#production-warning) section for full details.

Enterprise-grade Bitcoin ETF lifecycle platform with real-time NAV calculation, efficient settlement, and institutional-grade custody. Models institutional fund structures like iShares, Grayscale, and Blackrock Bitcoin ETFs.

The system implements blockchain-grade double-entry ledger accounting, transactional outbox event publishing, role-based access control with separation of duties, and a trust-boundary network model with only the API gateway exposed to the internet.

---

## Table of Contents

* [Quick Start](#quick-start)
* [Architecture](#architecture)
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
                     |  RBAC + rate-limit|
                     +----+-+-+-+--------+
                          | | | |
           DMZ network     | | | |internal network
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
      |Postgres | | Kafka    |        |  Bitcoin     |
      | :5432   | | :9092    |        |  Network     |
      +---------+ +----------+        | (read-only)  |
                        |             +------+-------+
              +---------+---+                 |
              |             |                 |
        +-----+------+  +---+-----+    +------+------+
        |  Compliance|  | Outbox  |    | Price Feed |
        |  Monitor   |  |Publisher|    | Oracle     |
        | :8005      |  |  :8010  |    | :8006      |
        +------------+  +---------+    +------------+
```

### Network Isolation

| Network | Services | Internet Access |
| --- | --- | --- |
| **dmz** | api-gateway, prometheus, grafana | Yes (host-reachable) |
| **internal** | All microservices, postgres, kafka, zookeeper, outbox-publisher | No (`internal: true`) |
| **blockchain** | price-feed-oracle | Bitcoin network peers (RPC) |

The API gateway bridges dmz and internal networks. The price feed oracle has read-only access to Bitcoin network. All other backend services operate in isolated internal network. No external connections except monitoring and fund operations.

### Infrastructure

| Component | Image | Purpose |
| --- | --- | --- |
| PostgreSQL | `postgres:16-alpine` | Persistent storage, immutable double-entry ledger |
| Kafka | `confluentinc/cp-kafka:7.6.0` | Event streaming between services |
| Zookeeper | `confluentinc/cp-zookeeper:7.6.0` | Kafka coordination |
| Prometheus | `prom/prometheus:v2.54.1` | Metrics collection (15s scrape interval) |
| Grafana | `grafana/grafana:11.2.0` | Dashboards and visualization |
| Bitcoin RPC | bitcoind (read-only peers) | Real-time Bitcoin blockchain data |

---

## Services

### API Gateway (port 8000)

The sole internet-facing service. Authenticates requests via `X-API-Key` header against SHA-256 hashed keys in the database, resolves the caller's role (admin, approver, trader, auditor), enforces rate limits (1,000 requests per 60-second sliding window per API key), and reverse-proxies to internal services. Every request is logged to the `audit.trail` Kafka topic with `X-Request-ID`, actor identity, IP address, and elapsed time.

**Routes:**

| Path Prefix | Upstream | Port |
| --- | --- | --- |
| `/v1/etf/*` | etf-issuer | 8001 |
| `/v1/custody/*` | bitcoin-custody | 8002 |
| `/v1/nav/*` | nav-engine | 8003 |
| `/v1/execution/*` | execution-engine | 8004 |
| `/v1/prices/*` | price-feed-oracle | 8006 |

`GET /health` aggregates health from all upstream services, returning `200` if all are healthy or `207` if any are degraded.

### ETF Issuer (port 8001)

Manages the complete lifecycle of Bitcoin ETF share creation, redemption, and tracking. Implements institutional fund accounting with per-share NAV tracking and in-kind redemption workflows.

* Validates KYC/AML status before issuance
* Supports idempotency keys to prevent duplicate processing
* 8-decimal-place precision for share tracking
* Creates matching debit/credit journal entries for all operations
* Publishes events via transactional outbox pattern
* Tracks per-share NAV to prevent dilution
* Manages creation basket composition (Bitcoin units per share creation)

**System accounts seeded at startup:**

| UUID | Name | Balance |
| --- | --- | --- |
| `...0001` | ETF_CAPITAL_RESERVE | 1000 BTC initial |
| `...0002` | CREATION_PROCEEDS | Receives fiat for creations |
| `...0003` | REDEMPTION_PROCEEDS | Holds BTC pending redemption |
| `...0004` | CUSTODY_OMNIBUS | Main Bitcoin custody account |

**Key operations:**

- `POST /v1/etf/creation` -- Authorized participants create new shares with in-kind Bitcoin
- `POST /v1/etf/redemption` -- Participants redeem shares for Bitcoin or fiat
- `GET /v1/etf/nav-per-share` -- Current fund NAV per share
- `GET /v1/etf/holdings` -- Bitcoin holdings, cash positions, fee accruals
- `GET /v1/etf/share-count` -- Total outstanding shares

### Bitcoin Custody (port 8002)

Manages secure custody of Bitcoin holdings with multi-signature controls and custody account segregation. Implements institutional-grade coin management with UTXO tracking and cold storage readiness.

* Maintains segregated custody accounts for each participant
* Tracks Bitcoin UTXO composition and dust amounts
* Advisory locks on custody accounts during transfers
* Row-level locking for atomic balance updates
* Implements min/max rebalancing thresholds
* Supports hot wallet and cold storage segregation

**Custody account types:**

- `omnibus` -- Commingled fund holdings
- `segregated` -- Participant-specific custody (optional)
- `trading` -- Execution hot wallet
- `cold_storage` -- Off-chain backup Bitcoin address

**Key operations:**

- `POST /v1/custody/deposit` -- Receive Bitcoin from participants
- `POST /v1/custody/withdraw` -- Send Bitcoin to participants
- `GET /v1/custody/balance/<account-id>` -- Current Bitcoin balance
- `GET /v1/custody/utxo-composition` -- UTXO distribution and dust tracking
- `POST /v1/custody/rebalance` -- Move funds between hot/cold storage

### NAV Engine (port 8003)

Real-time Net Asset Value calculation using live Bitcoin price feeds. Implements fund accounting rules with fee accruals, cash drag tracking, and timely NAV publication for listing exchanges.

* Consumes price updates from oracle every 10 seconds
* Calculates per-share NAV with 4-decimal precision
* Accrues management fees and performance fees daily
* Tracks cash drag from redemption proceeds
* Enforces minimum creation basket size
* Publishes NAV updates for exchange data feeds

**NAV calculation:**

```
NAV per share = (Total Fund Assets - Total Liabilities) / Shares Outstanding

Fund Assets = (Bitcoin Holdings × BTC Price) + Cash + Accrued Fees Receivable
Fund Liabilities = Fee Payables + Redemption Obligations
```

**Key operations:**

- `GET /v1/nav/current` -- Latest NAV per share
- `GET /v1/nav/intraday` -- Intraday NAV updates (refreshed 10s)
- `POST /v1/nav/accrue-fees` -- Daily fee accrual job
- `GET /v1/nav/composition` -- Breakdown of total fund value
- `GET /v1/nav/premium-discount` -- Market price vs NAV spread

### Execution Engine (port 8004)

Manages Bitcoin trading operations, rebalancing, and order execution. Interfaces with exchanges and OTC desks through pluggable settlement adapters.

* Executes creation basket trades on multiple venues
* Supports limit orders, market orders, and OTC trades
* Implements position reconciliation with trade confirmations
* Tracks execution quality metrics (VWAP, slippage)
* Supports multiple settlement methods (on-chain, exchange custody)
* Manages counterparty risk with trade limits

**Settlement rails:**

- `on_chain` -- Direct Bitcoin transfer
- `exchange_custody` -- Custody at exchange (Coinbase, Kraken, etc.)
- `otc_desk` -- OTC trade settlement with prime broker
- `institutional_settlement` -- Block trade settlement networks

**Key operations:**

- `POST /v1/execution/market-buy` -- Execute Bitcoin market buy
- `POST /v1/execution/limit-order` -- Place limit order
- `GET /v1/execution/order/<order-id>` -- Order status
- `POST /v1/execution/rebalance` -- Automated rebalancing sweep
- `GET /v1/execution/metrics` -- VWAP, slippage, cost analysis

### Price Feed Oracle (port 8006)

Aggregates Bitcoin prices from multiple sources (exchanges, data providers) and publishes canonical price for NAV calculation and compliance. Includes price validation and staleness checks.

* Consumes real-time BTC/USD prices from 5+ sources
* Applies median filtering to detect outliers
* Publishes canonical price every 10 seconds to Kafka
* Implements price staleness monitoring
* Supports fallback to previous close on data gaps
* Logs all price moves > 2% for compliance

**Supported price sources:**

- Coinbase Pro API (websocket)
- Kraken REST API (polling)
- CoinMarketCap historical prices
- Trading View real-time feeds
- CFTC settlement prices (fallback)

**Key operations:**

- `GET /v1/prices/btc-usd` -- Current canonical BTC/USD price
- `GET /v1/prices/historical` -- 1d/1h/15m OHLCV data
- `GET /v1/prices/sources` -- Price source health
- `POST /v1/prices/override` -- Manual price override (admin only)

### Compliance Monitor (port 8005)

Consumes ETF operations from Kafka and runs rule-based screening. Implements AML transaction screening and regulatory position reporting.

**Kafka topics consumed:**

`etf.creation.completed`, `etf.redemption.completed`, `custody.transfer.completed`, `execution.trade.completed`, `nav.updated`

**AML rules:**

| Rule | Threshold |
| --- | --- |
| Large creation (suspicious source) | >= $250,000 fiat in single creation |
| Velocity limit | > 20 creations per participant per hour |
| Structuring detection | Multiple creations < $10,000 each within 1 day |
| Redemption to high-risk address | Destination address flagged in Chainalysis/Elliptic |
| Concentration risk | Single participant > 5% of fund |

Risk scores range from 0 to 100. Results persisted to `compliance_events` and published to `compliance.event` Kafka topic (30-day retention).

### Outbox Publisher (port 8010)

Polls the `outbox_events` database table every 100ms for unpublished events and forwards them to Kafka. Uses `FOR UPDATE SKIP LOCKED` for safe horizontal scaling. Publishes with `acks=all` and marks events as published within the same transaction.

---

## Data Model

18 tables with PostgreSQL enums, check constraints, foreign keys, and immutability triggers.

### Core Tables

```
participants                        chart_of_accounts
  +- id (UUID PK)                    +- code (PK: ETF_CAPITAL_RESERVE,
  +- legal_name                             CREATION_PROCEEDS,
  +- participant_type (AP|retail)           REDEMPTION_PROCEEDS,
  +- kyc_verified                           CUSTODY_OMNIBUS,
  +- aml_cleared                            TRADING_WALLET,
  +- entity_classification                  CASH_SWEEP_ACCOUNT,
  +- risk_tier (1-5)                        FEE_REVENUE,
  +- creation_limit                         CUSTODY_PAYABLE)
  +- is_active                      +- normal_balance (debit|credit)
                                    +- description
api_keys
  +- key_hash (SHA-256, unique)
  +- role (admin|approver|trader|auditor)
  +- name
  +- is_active
```

### Fund Accounting Tables

```
etf_shares (IMMUTABLE - creation/redemption only via API)
  +- share_id (UUID PK)
  +- participant_id FK
  +- quantity NUMERIC(28,8)
  +- creation_price NUMERIC(18,8)
  +- issue_date
  +- redemption_request_id (nullable)

etf_fund_state
  +- shares_outstanding NUMERIC(28,8)
  +- bitcoin_holdings NUMERIC(28,8)  (in Satoshis)
  +- cash_balance NUMERIC(28,8)
  +- accrued_fees NUMERIC(28,8)
  +- nav_per_share NUMERIC(18,8)
  +- nav_timestamp

nav_history (IMMUTABLE)
  +- nav_date DATE
  +- nav_per_share NUMERIC(18,8)
  +- bitcoin_price NUMERIC(18,2)
  +- fund_assets NUMERIC(28,8)
  +- shares_outstanding NUMERIC(28,8)
  +- calculated_at
```

### Custody Tables

```
custody_accounts
  +- account_id (UUID PK)
  +- participant_id FK (nullable - NULL = omnibus)
  +- bitcoin_balance NUMERIC(28,8)  (in Satoshis)
  +- reserved NUMERIC(28,8)
  +- account_type (omnibus|segregated|trading|cold_storage)
  +- bip32_path (for HD wallet derivation)
  +- version (optimistic lock)

utxo_registry (IMMUTABLE)
  +- txid (Bitcoin transaction ID)
  +- vout (output index)
  +- satoshis NUMERIC(28,0)
  +- account_id FK
  +- confirmations
  +- is_dust (< 546 satoshis)
  +- status (spendable|pending|spent)
```

### Trading & Execution Tables

```
creation_requests
  +- creation_id (unique)
  +- participant_id FK
  +- bitcoin_amount NUMERIC(28,8)
  +- fiat_amount NUMERIC(28,2)
  +- shares_issued NUMERIC(28,8)
  +- nav_per_share_at_creation NUMERIC(18,8)
  +- status (pending|settled|failed|cancelled)
  +- request_id

execution_trades
  +- trade_ref (unique)
  +- order_type (market|limit|otc)
  +- side (buy|sell)
  +- bitcoin_amount NUMERIC(28,8)
  +- execution_price NUMERIC(18,8)
  +- total_cost NUMERIC(28,2)
  +- venue (exchange name or OTC desk)
  +- settlement_method (on_chain|exchange|otc)
  +- trade_status

bitcoin_prices (IMMUTABLE)
  +- timestamp TIMESTAMP
  +- price_usd NUMERIC(18,2)
  +- source (coinbase|kraken|cmc|other)
  +- is_canonical BOOLEAN
  +- volume_24h NUMERIC(28,2)
  +- market_cap NUMERIC(38,2)
```

### Status & Compliance Tables

```
creation_status_history (IMMUTABLE)
  +- creation_id FK
  +- previous_status
  +- new_status
  +- actor_id FK
  +- actor_service
  +- transition_reason
  +- created_at

compliance_events
  +- entity_type (participant|creation|trade|custody_transfer)
  +- entity_id
  +- rule_violated (or 'clean')
  +- risk_score NUMERIC(5,2)
  +- details (JSONB)
  +- created_at

outbox_events (IMMUTABLE payload)
  +- id (UUID PK)
  +- aggregate_id
  +- event_type (Kafka topic)
  +- payload (JSONB)
  +- published_at (NULL until outbox-publisher processes)
  +- created_at
```

**Supported currencies:** USD, EUR, GBP, JPY
**Bitcoin denominations:** Satoshi (1 BTC = 100,000,000 satoshis)

---

## Kafka Topics

18 topics provisioned at startup with LZ4 compression.

| Topic | Partitions | Retention | Purpose |
| --- | --- | --- | --- |
| `etf.creation.requested` | 4 | 7d | Creation order queued by AP |
| `etf.creation.completed` | 4 | 7d | Shares minted, Bitcoin received |
| `etf.redemption.requested` | 4 | 7d | Redemption order submitted |
| `etf.redemption.completed` | 4 | 7d | Shares burned, Bitcoin released |
| `etf.nav.updated` | 8 | 7d | NAV per share recalculated |
| `custody.deposit.initiated` | 4 | 7d | Bitcoin deposit pending confirmation |
| `custody.deposit.confirmed` | 4 | 7d | Bitcoin received and credited |
| `custody.withdrawal.initiated` | 4 | 7d | Bitcoin withdrawal processing |
| `custody.withdrawal.confirmed` | 4 | 7d | Bitcoin sent, on-chain confirmed |
| `execution.trade.submitted` | 4 | 7d | Trade order placed |
| `execution.trade.completed` | 4 | 7d | Trade settled and executed |
| `execution.trade.failed` | 2 | 1d | Trade execution failed |
| `bitcoin.price.updated` | 2 | 7d | New canonical Bitcoin price |
| `compliance.screening.completed` | 4 | 30d | AML/sanctions screening results |
| `audit.trail` | 8 | 30d | Immutable request audit log |
| `dlq.default` | 2 | 30d | Dead letter queue for failed messages |

---

## API Reference

All requests go through the API gateway at `http://localhost:8000`. Include the API key as `X-API-Key` header.

**Seeded API keys (demo only):**

| Key | Role | Purpose |
| --- | --- | --- |
| Value from `GATEWAY_API_KEY` env var | admin | Full access |
| `trader-key-demo-001` | trader | Submit orders, manage creations/redemptions |
| `auditor-key-demo-001` | auditor | Read-only access to balances and pricing |

### ETF Creation & Redemption

```bash
# Get current fund state
curl http://localhost:8000/v1/etf/fund-state \
  -H "X-API-Key: $API_KEY"

# Get current NAV per share
curl http://localhost:8000/v1/etf/nav-per-share \
  -H "X-API-Key: $API_KEY"

# Submit creation order (in-kind: send Bitcoin, receive shares)
curl -X POST http://localhost:8000/v1/etf/creation \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": "<participant-uuid>",
    "bitcoin_amount": "10.5",
    "idempotency_key": "CREATE-20240615-001"
  }'

# Submit redemption order (send shares, receive Bitcoin)
curl -X POST http://localhost:8000/v1/etf/redemption \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": "<participant-uuid>",
    "share_quantity": "1000.00",
    "redemption_method": "bitcoin",
    "idempotency_key": "REDEEM-20240615-001"
  }'

# Get participant holdings
curl http://localhost:8000/v1/etf/holdings/<participant-id> \
  -H "X-API-Key: $API_KEY"

# Get creation/redemption history
curl "http://localhost:8000/v1/etf/creations?limit=50&offset=0" \
  -H "X-API-Key: $API_KEY"
```

### Custody Management

```bash
# Get custody balance
curl http://localhost:8000/v1/custody/balance/<account-id> \
  -H "X-API-Key: $API_KEY"

# Get UTXO composition
curl http://localhost:8000/v1/custody/utxo-composition \
  -H "X-API-Key: $API_KEY"

# Deposit Bitcoin (receiving address)
curl -X POST http://localhost:8000/v1/custody/deposit \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "from_address": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    "amount_satoshis": "1000000",
    "deposit_id": "DEP-20240615-001"
  }'

# Withdraw Bitcoin (sending address)
curl -X POST http://localhost:8000/v1/custody/withdraw \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to_address": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    "amount_satoshis": "500000",
    "withdrawal_id": "WD-20240615-001"
  }'

# Rebalance hot/cold storage
curl -X POST http://localhost:8000/v1/custody/rebalance \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_hot_wallet_btc": "50",
    "priority": "normal"
  }'
```

### NAV & Pricing

```bash
# Get current NAV per share
curl http://localhost:8000/v1/nav/current \
  -H "X-API-Key: $API_KEY"

# Get intraday NAV updates (10s refresh)
curl http://localhost:8000/v1/nav/intraday \
  -H "X-API-Key: $API_KEY"

# Get fund composition
curl http://localhost:8000/v1/nav/composition \
  -H "X-API-Key: $API_KEY"

# Get Bitcoin price
curl http://localhost:8000/v1/prices/btc-usd \
  -H "X-API-Key: $API_KEY"

# Get historical OHLCV data
curl "http://localhost:8000/v1/prices/historical?interval=1h&limit=24" \
  -H "X-API-Key: $API_KEY"

# Get price source health
curl http://localhost:8000/v1/prices/sources \
  -H "X-API-Key: $API_KEY"
```

### Execution & Trading

```bash
# Execute market buy
curl -X POST http://localhost:8000/v1/execution/market-buy \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "bitcoin_amount": "5.0",
    "venue": "coinbase",
    "settlement_method": "on_chain",
    "trade_id": "TRADE-20240615-001"
  }'

# Place limit order
curl -X POST http://localhost:8000/v1/execution/limit-order \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "side": "buy",
    "bitcoin_amount": "2.5",
    "limit_price": "62500.00",
    "venue": "kraken",
    "order_id": "ORDER-20240615-001"
  }'

# Get order status
curl http://localhost:8000/v1/execution/order/<order-id> \
  -H "X-API-Key: $API_KEY"

# Get execution metrics
curl http://localhost:8000/v1/execution/metrics \
  -H "X-API-Key: $API_KEY"

# Trigger rebalancing
curl -X POST http://localhost:8000/v1/execution/rebalance \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_hot_wallet_btc": "50",
    "rebalance_id": "RB-20240615-001"
  }'
```

### Health

```bash
# Gateway health (aggregates all services)
curl http://localhost:8000/health
```

---

## Getting Started

### Prerequisites

* Docker and Docker Compose
* 2 GB RAM minimum (Kafka + PostgreSQL + 6 services)
* Bitcoin RPC endpoint (or use mock in development mode)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set values:

```bash
POSTGRES_PASSWORD=<strong-password>
GATEWAY_API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
GRAFANA_PASSWORD=<grafana-password>
BTC_RPC_URL=http://localhost:18332  # testnet or regtest
PRICE_FEED_API_KEY=<coinbase-api-key>
```

### 2. Start the platform

```bash
make build
make up
```

This starts 10 containers:

1. **postgres** -- database with schema and seed data
2. **zookeeper** -- Kafka coordination
3. **kafka** -- event broker
4. **kafka-init** -- creates 18 topics, then exits
5. **etf-issuer** -- fund share creation/redemption
6. **bitcoin-custody** -- Bitcoin custody management
7. **nav-engine** -- Net Asset Value calculation
8. **execution-engine** -- Bitcoin trading operations
9. **price-feed-oracle** -- Bitcoin price aggregation
10. **compliance-monitor** -- AML/regulatory screening
11. **outbox-publisher** -- event relay to Kafka
12. **api-gateway** -- reverse proxy (waits for all services healthy)
13. **prometheus** + **grafana** -- observability

### 3. Verify

```bash
# Check containers running
docker compose ps

# Test gateway health
curl http://localhost:8000/health

# Expected: all services report "ok"
```

### 4. Run the demo

```bash
make demo
```

This executes a complete ETF lifecycle: participant onboarding, Bitcoin deposit, share creation, NAV calculation, trading operations, redemption, and compliance screening.

### Teardown

```bash
make down        # Stop but keep volumes
make down-v      # Stop and remove volumes (full reset)
```

---

## Monitoring

| Service | URL | Credentials |
| --- | --- | --- |
| Prometheus | <http://localhost:9090> | None |
| Grafana | <http://localhost:3000> | admin / `$GRAFANA_PASSWORD` |

Each microservice exposes a `/metrics` endpoint scraped every 15 seconds.

**Metrics collected:**

| Metric | Type | Labels |
| --- | --- | --- |
| `http_requests_total` | Counter | service, method, path, status_code |
| `http_request_duration_seconds` | Histogram | service, method, path |
| `etf_creations_total` | Counter | status |
| `etf_redemptions_total` | Counter | status |
| `etf_shares_outstanding` | Gauge | - |
| `etf_nav_per_share` | Gauge | - |
| `bitcoin_holdings_satoshis` | Gauge | - |
| `custody_hot_wallet_balance` | Gauge | - |
| `execution_trades_total` | Counter | venue, status |
| `bitcoin_price_usd` | Gauge | source |
| `price_feed_staleness_seconds` | Gauge | - |
| `compliance_screenings_total` | Counter | result |
| `kafka_publishes_total` | Counter | topic, status |
| `kafka_publish_latency_seconds` | Histogram | topic |

---

## Scripts and Utilities

| Script | Purpose |
| --- | --- |
| `scripts/demo.py` | End-to-end demo: onboarding, creation, redemption, trading, NAV calculation |
| `scripts/load_test.py` | Concurrent creation/redemption load testing |
| `scripts/fund_integrity.py` | Fund accounting audit: share count, Bitcoin balances, NAV reconciliation |
| `scripts/kafka_tail.py` | Real-time Kafka topic monitoring |

### Makefile Targets

```bash
make help              # Show all targets
make build             # Build all images
make up                # Start all containers
make down              # Stop containers
make down-v            # Stop and remove volumes
make demo              # Run full ETF lifecycle demo
make logs              # Follow all service logs
make logs-svc SVC=etf-issuer  # Follow one service
make ps                # Show container status
make health            # Check gateway health
make test              # Run test suite
make integrity         # Fund accounting integrity check
make db-balances       # Show fund balances
make db-shares         # Show share outstanding
make db-nav-history    # Show NAV history
make shell-pg          # PostgreSQL shell
make shell-kafka       # Kafka shell
make topics            # List Kafka topics
make open-docs         # Open API docs
```

---

## Technical Design

### Double-Entry Ledger for Fund Accounting

Every fund operation (creation, redemption, fee accrual) creates debit and credit journal entries. The chart of accounts defines normal balance convention:

**Assets** (OMNIBUS_RESERVE, TRADING_WALLET): `SUM(debit) - SUM(credit)`
**Liabilities** (CUSTODY_PAYABLE, FEE_PAYABLE): `SUM(credit) - SUM(debit)`

Fund net asset value is directly derived from ledger balances, ensuring accounting integrity.

### Immutability Enforcement

Database triggers prevent UPDATE/DELETE on critical tables:

| Table | Protection | Behavior |
| --- | --- | --- |
| `journal_entries` | Immutable | Cannot modify after insertion |
| `utxo_registry` | Immutable | UTXO history preserved |
| `nav_history` | Immutable | NAV history never revised |
| `outbox_events` | Semi-immutable | Only `published_at` can be updated |

### ETF Lifecycle State Machine

```
Creation:  pending -> processing -> settled -> completed
Redemption: pending -> processing -> settled -> completed
NAV:       calculated -> published -> finalized
```

State transitions enforce valid workflows and prevent race conditions.

### Role-Based Access Control

| Role | Permissions |
| --- | --- |
| `admin` | Full system access |
| `trader` | Submit orders, manage creations/redemptions |
| `approver` | Approve large operations |
| `auditor` | Read-only access |

### Transactional Outbox Pattern

Business operations and event publishing happen in a single database transaction:

1. Service performs fund operation (create, redeem, accrue fees)
2. Service writes event to `outbox_events` table
3. Transaction commits atomically
4. `outbox-publisher` polls and relays events to Kafka asynchronously

Guarantees at-least-once event delivery without distributed transactions.

### Bitcoin Price Aggregation

Multiple price sources (Coinbase, Kraken, CoinMarketCap) are consumed and validated:

1. Each source provides BTC/USD price every 10 seconds
2. Median filtering detects and removes outliers
3. Staleness check ensures prices < 30 seconds old
4. Canonical price published to Kafka `bitcoin.price.updated` topic
5. NAV engine consumes canonical price for fund valuation

### NAV Per Share Calculation

```
Total Fund Assets = (Bitcoin Holdings × BTC Price) + Cash + Accrued Fees
Total Fund Liabilities = Fee Payables + Redemption Obligations

NAV per Share = Total Assets / Shares Outstanding
```

Precision: 8 decimal places for Bitcoin, 2 decimal places for USD values.

### UTXO Coin Management

The system tracks individual UTXOs from Bitcoin blockchain:

- Each UTXO is immutable and tracked in `utxo_registry`
- Dust amounts (< 546 satoshis) are flagged but retained
- Hot wallet maintains minimum UTXO set for fast withdrawals
- Cold storage holds accumulated UTXOs
- Rebalancing sweeps consolidate UTXOs to optimize fees

### Concurrency Control

* **Advisory locks:** `pg_advisory_xact_lock` on account+currency prevents double-spend
* **Row-level locking:** `SELECT FOR UPDATE` on custody accounts
* **Optimistic locking:** Version column on `etf_fund_state` prevents conflicting updates
* **Skip-locked queues:** RTGS processor uses `SKIP LOCKED` for multi-worker safety

---

## Project Structure

```
Bitcoin-ETF/
+-- docker-compose.yml
+-- Makefile
+-- .env.example
+-- LICENSE
+-- README.md
+-- services/
|   +-- api-gateway/           # RBAC auth, rate limiting, reverse proxy
|   +-- etf-issuer/            # Share creation/redemption, fund accounting
|   +-- bitcoin-custody/       # Bitcoin custody, UTXO tracking
|   +-- nav-engine/            # NAV calculation, fee accrual
|   +-- execution-engine/      # Bitcoin trading operations
|   +-- price-feed-oracle/     # Price aggregation, canonical feed
|   +-- compliance-monitor/    # AML screening, regulatory checks
|   +-- outbox-publisher/      # Event relay to Kafka
+-- init/
|   +-- postgres/
|       +-- 01_schema.sql      # Base schema, enums, seed data
|       +-- 02_migrations.sql  # Indexes, triggers, RBAC
|   +-- kafka/
|       +-- create_topics.sh   # 18 topics with retention policies
+-- scripts/
|   +-- demo.py                # End-to-end lifecycle demo
|   +-- load_test.py           # Concurrent load testing
|   +-- fund_integrity.py      # Fund accounting audit
|   +-- kafka_tail.py          # Real-time topic monitoring
+-- tests/
    +-- conftest.py
    +-- test_etf_issuer.py
    +-- test_custody.py
    +-- test_nav_engine.py
    +-- test_execution.py
    +-- test_compliance.py
    +-- test_e2e_lifecycle.py
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
| Custody account segregation audit | Commingled funds, participant claims on failure |
| Real KYC/AML provider integration (Onfido, Chainalysis) | No identity verification or sanctions screening |
| Regulatory reporting (Form 13F, daily NAV publication) | SEC violations |
| Blockchain transaction signing (hardware wallet) | No cryptographic key security |
| Fund accounting audit (Big 4 audit firm) | Unaudited financial statements |
| Insurance (crime, custody liability) | No coverage for Bitcoin loss |
| Catastrophe recovery procedures | No tested failover for fund operations |
| Daily NAV reconciliation | No control matching fund state to blockchain |

> Bitcoin ETFs at institutional scale require: SEC registration, real custody partnerships, real exchange memberships, regulatory approval from relevant authorities (SEC, CFTC), KYC/AML infrastructure, and legal agreements with all participants. **Do not use this code to issue, manage, or trade any real Bitcoin or launch an actual ETF fund.**

---

## License

This project is provided as-is for educational and reference purposes under the MIT License.

---

*Built with ♥️ by Pavon Dunbar -- Modeled on institutional Bitcoin ETF systems (iShares IBIT, Grayscale GBTC, Blackrock GBTC)*
