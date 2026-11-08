import time
from fastapi import FastAPI, HTTPException, status, Request
from pydantic import BaseModel, Field
from app.rate_limiter import evaluate_rate_limit

app = FastAPI(
    title="AegisMesh Control Plane Proxy",
    description="Asynchronous rate-limiting and resilience gateway for AI Agent tool calls",
    version="0.1.0"
)

class ToolCallRequest(BaseModel):
    agent_id: str = Field(..., example="agent_alpha")
    tool_name: str = Field(..., example="execute_sql_query")
    payload: dict = Field(default_factory=dict)

# Middleware for measuring proxy overhead latency
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-AegisMesh-Latency-MS"] = f"{process_time_ms:.2f}"
    return response

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "system": "AegisMesh Gate"}

@app.post("/v1/execute")
async def execute_tool(request: ToolCallRequest):
    allowed, remaining = evaluate_rate_limit(request.agent_id, request.tool_name)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "AegisMesh Rate Limit Tripped",
                "reason": "Agent infinite loop detected or per-tool capacity exceeded.",
                "agent_id": request.agent_id,
                "tool_name": request.tool_name
            }
        )

    return {
        "status": "ALLOWED",
        "agent_id": request.agent_id,
        "tool_name": request.tool_name,
        "remaining_tokens": remaining,
        "output": f"Simulated execution of {request.tool_name} completed."
    }
