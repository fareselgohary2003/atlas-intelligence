"""Rate limiting: in-process sliding window, or Redis fixed window. SafeLimiter falls back to the in-process limiter (and logs)
if Redis fails, so an outage degrades protection to per-process instead of taking the API down."""
import hashlib
import logging
import threading
import time
from collections import defaultdict, deque

log = logging.getLogger("atlas.ratelimit")


class MemoryLimiter:
    def __init__(self, clock=time.monotonic):
        self._hits, self._lock, self.clock = defaultdict(deque), threading.Lock(), clock

    def hit(self, key: str, limit: int, window: int):
        """-> (allowed, retry_after_seconds)"""
        with self._lock:
            q, now = self._hits[key], self.clock()
            while q and now - q[0] >= window:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, int(window - (now - q[0])) + 1)
            q.append(now)
            return True, 0

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)


class RedisLimiter:
    def __init__(self, client, prefix="atlas:rl:"):
        self.client, self.prefix = client, prefix

    def hit(self, key, limit, window):
        k = self.prefix + key
        n = self.client.incr(k)
        if n == 1:
            self.client.expire(k, window)
        if n > limit:
            ttl = self.client.ttl(k)
            return False, ttl if isinstance(ttl, int) and ttl > 0 else window
        return True, 0

    def reset(self, key):
        self.client.delete(self.prefix + key)


class SafeLimiter:
    def __init__(self, primary, fallback=None):
        self.primary, self.fallback = primary, fallback or MemoryLimiter()

    def hit(self, key, limit, window):
        try:
            return self.primary.hit(key, limit, window)
        except Exception:
            log.exception("rate limiter backend failed; using in-process fallback")
            return self.fallback.hit(key, limit, window)

    def reset(self, key):
        for lim in (self.primary, self.fallback):
            try:
                lim.reset(key)
            except Exception:
                log.exception("rate limiter reset failed")


def create_limiter(env):
    url = env.get("REDIS_URL")
    if url:
        try:
            import redis
            client = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
            client.ping()
            return SafeLimiter(RedisLimiter(client))
        except Exception:
            log.warning("Redis unavailable for rate limiting; using in-process limiter")
    return SafeLimiter(MemoryLimiter())


def account_key(email: str) -> str:
    return "login:acct:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()[:32]  # emails are never stored in limiter keys
