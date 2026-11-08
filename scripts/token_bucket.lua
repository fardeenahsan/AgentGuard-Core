-- KEYS[1]: rate limit key (e.g. rate_limit:agent_123:db_tool)
-- ARGV[1]: capacity (max tokens)
-- ARGV[2]: refill_rate (tokens per second)
-- ARGV[3]: current_timestamp (seconds)

local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call("HMGET", key, "tokens", "last_updated")
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if not tokens or not last_updated then
    tokens = capacity - 1
    last_updated = now
    redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
    redis.call("EXPIRE", key, 3600)
    return {1, math.floor(tokens)}
end

-- Calculate elapsed time and refilled tokens
local elapsed = now - last_updated
tokens = math.min(capacity, tokens + (elapsed * refill_rate))

if tokens >= 1.0 then
    tokens = tokens - 1.0
    last_updated = now
    redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
    return {1, math.floor(tokens)}
else
    return {0, 0}
end