"""An in-memory request limiter: per IP per minute, and a total per day.

Fixed windows: the counts reset when the clock enters a new minute or a new day (UTC).
They also reset when the server restarts, and the client IP comes from a header that can
be spoofed. Both are acceptable for a free demo; the README says so.
"""

import threading
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    per_minute: int  # requests one IP may make in one minute
    per_day: int  # requests all IPs together may make in one day
    current_minute: int = -1
    current_day: int = -1
    requests_this_minute: dict[str, int] = field(default_factory=dict)
    requests_today: int = 0
    # FastAPI runs plain `def` endpoints in a thread pool, so two requests can arrive at once.
    lock: threading.Lock = field(default_factory=threading.Lock)


def allow_request(limiter: RateLimiter, client_ip: str, now: float) -> bool:
    """Count one request at time `now` (seconds since the epoch); False if over a limit."""
    minute, day = int(now // 60), int(now // 86_400)
    with limiter.lock:
        if minute != limiter.current_minute:
            limiter.current_minute, limiter.requests_this_minute = minute, {}
        if day != limiter.current_day:
            limiter.current_day, limiter.requests_today = day, 0
        from_this_ip = limiter.requests_this_minute.get(client_ip, 0)
        if from_this_ip >= limiter.per_minute or limiter.requests_today >= limiter.per_day:
            return False
        limiter.requests_this_minute[client_ip] = from_this_ip + 1
        limiter.requests_today += 1
        return True
