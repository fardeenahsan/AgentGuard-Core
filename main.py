import ctypes
import os
import time
from fastapi import FastAPI, HTTPException, status, Response
from pydantic import BaseModel

app = FastAPI(title="AgentGuard-Core Gateway", version="1.0.0")

# Load the compiled C++ circuit breaker shared library
lib_path = os.getenv("CB_LIB_PATH", "./libcircuit.so")
try:
    _lib = ctypes.CDLL(lib_path)
    
    _lib.create_circuit_breaker.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    _lib.create_circuit_breaker.restype = ctypes.c_void_p
    
    _lib.cb_allow_request.argtypes = [ctypes.c_void_p]
    _lib.cb_allow_request.restype = ctypes.c_bool
    
    _lib.cb_record_success.argtypes = [ctypes.c_void_p]
    _lib.cb_record_failure.argtypes = [ctypes.c_void_p]
    
    db_circuit = _lib.create_circuit_breaker(b"database_service", 3, 10)
except Exception as e:
    print(f"[Warning] C++ Circuit Breaker library not loaded: {e}. Running in passthrough mode.")
    db_circuit = None

class AgentRequest(BaseModel):
    agent_id: str
    tool_name: str
    payload: dict

@app.post("/v1/execute")
async def execute_tool(req: AgentRequest, response: Response):
    start_time = time.perf_counter()
    
    # Updated Telemetry Headers
    response.headers["X-AgentGuard-Gateway"] = "Active"
    
    # 1. C++ Circuit Breaker Check
    if db_circuit and not _lib.cb_allow_request(db_circuit):
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-AgentGuard-Latency-MS"] = f"{elapsed_ms:.4f}"
        response.headers["X-AgentGuard-Circuit-State"] = "OPEN"
        
        print(f"[AgentGuard Telemetry] FAST-FAIL | Agent: {req.agent_id} | Tool: {req.tool_name} | Latency: {elapsed_ms:.4f}ms")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Circuit Breaker OPEN: Downstream service failing."
        )

    try:
        if db_circuit:
            _lib.cb_record_success(db_circuit)
            
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-AgentGuard-Latency-MS"] = f"{elapsed_ms:.4f}"
        response.headers["X-AgentGuard-Circuit-State"] = "CLOSED"
        
        print(f"[AgentGuard Telemetry] SUCCESS | Agent: {req.agent_id} | Tool: {req.tool_name} | Latency: {elapsed_ms:.4f}ms")
        
        return {
            "status": "ALLOWED",
            "agent_id": req.agent_id,
            "tool_name": req.tool_name,
            "message": "Tool executed safely through AgentGuard-Core."
        }
        
    except Exception as e:
        if db_circuit:
            _lib.cb_record_failure(db_circuit)
            
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-AgentGuard-Latency-MS"] = f"{elapsed_ms:.4f}"
        response.headers["X-AgentGuard-Circuit-State"] = "TRIPPED"
        
        print(f"[AgentGuard Telemetry] ERROR | Agent: {req.agent_id} | Tool: {req.tool_name} | Latency: {elapsed_ms:.4f}ms")
        raise HTTPException(status_code=500, detail=str(e))