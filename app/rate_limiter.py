import time
import redis
from app.config import REDIS_HOST, REDIS_PORT, DEFAULT_BUCKET_CAPACITY, DEFAULT_REFILL_RATE

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Load Lua script into Redis
with open("scripts/token_bucket.lua", "r") as f:
    lua_script = f.read()
token_bucket_script = r.register_script(lua_script)

def evaluate_rate_limit(agent_id: str, tool_name: str) -> tuple[bool, int]:
    key = f"rate_limit:{agent_id}:{tool_name}"
    now = time.time()

    # Execute atomic evaluation
    allowed, remaining = token_bucket_script(
        keys=[key],
        args=[DEFAULT_BUCKET_CAPACITY, DEFAULT_REFILL_RATE, now]
    )
    return bool(allowed), int(remaining)
