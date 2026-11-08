# agentguard-core

A high-performance, multi-language resilience middleware and control plane for autonomous AI agents. Designed to sit between agent orchestration frameworks and downstream tools, preventing cascading failures, unbounded API costs, and race conditions under heavy concurrent load.

---

## Architecture & Problem Statement

Autonomous agents frequently trigger unconstrained tool calls (database queries, external REST APIs, LLM sub-invocations). Without proper backpressure, a single failing downstream dependency can cause resource exhaustion across the entire cluster. 

`agentguard-core` provides a low-overhead proxy layer enforcing two core safety invariants:
1. **Atomic Rate Limiting** to control token consumption and throughput per agent.
2. **Circuit Breaking** to fast-fail traffic during downstream degradation without incurring garbage collection or interpreter lock overhead.

```
[ AI Agent Runtime ]
        │
        ▼ (HTTP POST /v1/execute)
[ FastAPI Async Gateway ]
        ├──► [ Redis (Lua Scripting) ] ───► Atomic Token Bucket Rate Limiter
        └──► [ C++ State Machine (`libcircuit.so`) ] ───► O(1) Memory-Safe Circuit Breaker via FFI (`ctypes`)
```

---

## Core Technical Decisions & Trade-Offs

### 1. C++ FFI (`ctypes`) over Pure Python for State Management
* **The Problem:** Python's Global Interpreter Lock (GIL) and garbage collection pauses introduce unpredictable latency variance when evaluating high-frequency state machine transitions under concurrent request loads.
* **The Solution:** The circuit breaker state machine is written in native C++, compiled into a shared library (`libcircuit.so`) with `-O3` optimization, and bound directly via Python `ctypes`. This guarantees $O(1)$ state evaluation with zero managed-runtime overhead during hot-path checks.

### 2. Redis + Lua for Distributed Rate Limiting
* **The Problem:** Standard check-then-set application logic in Python creates race conditions under high concurrency, leading to rate-limit leakage.
* **The Solution:** The token bucket algorithm is implemented entirely inside an atomic **Redis Lua script**. Redis executes the script atomically, ensuring zero race conditions across multiple gateway replicas without locking the application layer.

---

## Technical Stack

* **Gateway & Routing:** Python 3.11, FastAPI, Uvicorn (Async I/O event loop)
* **Core Runtime / FFI:** C++, POSIX threads, `g++` (`-fPIC -shared -O3`)
* **State & Concurrency Control:** Redis 7, Lua scripting
* **Containerization:** Docker, multi-stage builds, Docker Compose

---

## Project Layout

```text
agentguard-core/
├── main.py               # FastAPI application & FFI bindings
├── circuit.cpp           # Native C++ circuit breaker state machine
├── libcircuit.so         # Compiled shared object binary
├── Dockerfile            # Container build instructions & C++ compiler pipeline
├── docker-compose.yml    # Local multi-service orchestration (Gateway + Redis)
├── requirements.txt      # Python dependencies
└── README.md
```

---

## Quick Start (Docker)

Ensure Docker and Docker Compose are installed, then run:

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/agentguard-core.git
cd agentguard-core

# Build and spin up the containerized stack
docker compose up --build -d
```

### Verifying Gateway Health & Telemetry

Send a test payload through the gateway:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/v1/execute" -Method Post -ContentType "application/json" -Body '{"agent_id": "agent_alpha", "tool_name": "db", "payload": {}}'
```

**Expected Response:**
```text
status          : ALLOWED
agent_id        : agent_alpha
tool_name       : db
remaining_tokens: 4
output          : Simulated execution of db completed.
```

---

## Telemetry & Observability Headers

Every request processed through the gateway injects low-overhead debugging and MLOps headers for real-time tracing:

* `X-AgentGuard-Gateway`: Confirms active routing through the control plane.
* `X-AgentGuard-Latency-MS`: Microsecond-precision execution tracking.
* `X-AgentGuard-Circuit-State`: Real-time state of downstream tool connections (`CLOSED`, `OPEN`, `TRIPPED`).

---

## License

Distributed under the MIT License.