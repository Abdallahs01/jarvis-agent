"""
Rate limiting setup (slowapi, in-memory backend).

In-memory means limits reset on restart and aren't shared across
multiple worker processes/replicas -- the same Phase 1 tradeoff as the
in-memory conversation store. Fine for a single-instance deployment
(which is what the free Render tier gives you); if this ever runs with
more than one worker, slowapi's Redis storage backend is the drop-in
upgrade path (change one line here, nothing else).

Keyed by client IP rather than the API key: it's simpler, and the goal
is guarding against runaway/accidental request floods (e.g. a retry
loop gone wrong) rather than per-tenant billing, which doesn't apply
with a single shared API key.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
