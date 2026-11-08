import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
DEFAULT_BUCKET_CAPACITY = int(os.getenv("DEFAULT_BUCKET_CAPACITY", 5))
DEFAULT_REFILL_RATE = float(os.getenv("DEFAULT_REFILL_RATE", 1.0))  # 1 token/sec
