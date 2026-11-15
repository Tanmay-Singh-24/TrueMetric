from orderlens.ratelimit import RateLimiter, allow_request

NOON = 1_800_000_000.0  # an arbitrary moment, in seconds since the epoch


def test_an_ip_is_stopped_after_its_per_minute_limit() -> None:
    limiter = RateLimiter(per_minute=2, per_day=100)
    results = [allow_request(limiter, "1.1.1.1", NOON) for _ in range(3)]
    assert results == [True, True, False]


def test_each_ip_has_its_own_minute_limit() -> None:
    limiter = RateLimiter(per_minute=1, per_day=100)
    allow_request(limiter, "1.1.1.1", NOON)
    assert allow_request(limiter, "2.2.2.2", NOON)


def test_the_minute_limit_resets_in_the_next_minute() -> None:
    limiter = RateLimiter(per_minute=1, per_day=100)
    allow_request(limiter, "1.1.1.1", NOON)
    assert allow_request(limiter, "1.1.1.1", NOON + 60)


def test_the_daily_limit_counts_all_ips_together() -> None:
    limiter = RateLimiter(per_minute=10, per_day=2)
    allow_request(limiter, "1.1.1.1", NOON)
    allow_request(limiter, "2.2.2.2", NOON)
    assert not allow_request(limiter, "3.3.3.3", NOON)


def test_a_refused_request_is_not_counted() -> None:
    limiter = RateLimiter(per_minute=1, per_day=100)
    allow_request(limiter, "1.1.1.1", NOON)
    allow_request(limiter, "1.1.1.1", NOON + 1)
    assert limiter.requests_today == 1
