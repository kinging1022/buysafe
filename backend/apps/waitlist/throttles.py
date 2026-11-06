from rest_framework.throttling import ScopedRateThrottle


class WaitlistDailyThrottle(ScopedRateThrottle):
    """A second scoped rate on the same view, read from `throttle_scope_daily`."""

    scope_attr = 'throttle_scope_daily'
