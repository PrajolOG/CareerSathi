"""
In-memory sliding-window rate limiter.

Tracks timestamps of actions in a dict keyed by identifier (IP or user_id).
On each check, prunes timestamps older than the window, then evaluates the count.

Survives page reloads (server-side memory). Resets only on server restart.
"""

import time
import threading

# ---------- Storage ----------
_login_attempts: dict[str, list[float]] = {}   # IP -> timestamps
_chat_messages: dict[str, list[float]] = {}    # user_id -> timestamps
_lock = threading.Lock()

# ---------- Limits ----------
LOGIN_MAX = 5        # attempts
LOGIN_WINDOW = 60    # seconds

CHAT_MAX = 10        # messages
CHAT_WINDOW = 60     # seconds


def _prune_and_check(
    store: dict[str, list[float]],
    identifier: str,
    max_count: int,
    window: int,
) -> tuple[bool, int]:
    """
    Returns (allowed: bool, retry_after: int seconds).
    If allowed is True, the action is recorded.
    """
    now = time.time()
    cutoff = now - window

    with _lock:
        timestamps = store.get(identifier, [])
        # Remove expired entries
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= max_count:
            # Calculate when the oldest entry in window expires
            oldest = timestamps[0]
            retry_after = int(oldest + window - now) + 1
            store[identifier] = timestamps
            return False, max(retry_after, 1)

        # Record this action
        timestamps.append(now)
        store[identifier] = timestamps
        return True, 0


def _get_remaining(
    store: dict[str, list[float]],
    identifier: str,
    max_count: int,
    window: int,
) -> tuple[int, bool, int]:
    """
    Returns (remaining: int, is_limited: bool, retry_after: int)
    Does NOT record any action.
    """
    now = time.time()
    cutoff = now - window

    with _lock:
        timestamps = store.get(identifier, [])
        timestamps = [t for t in timestamps if t > cutoff]
        store[identifier] = timestamps

        count = len(timestamps)
        remaining = max(0, max_count - count)
        is_limited = count >= max_count

        retry_after = 0
        if is_limited and timestamps:
            oldest = timestamps[0]
            retry_after = int(oldest + window - now) + 1
            retry_after = max(retry_after, 1)

        return remaining, is_limited, retry_after


# ---------- Public API ----------

def check_login_rate_limit(ip: str) -> tuple[bool, int]:
    """Check and record a login attempt. Returns (allowed, retry_after_seconds)."""
    return _prune_and_check(_login_attempts, ip, LOGIN_MAX, LOGIN_WINDOW)


def check_chat_rate_limit(user_id: str) -> tuple[bool, int]:
    """Check and record a chat message. Returns (allowed, retry_after_seconds)."""
    return _prune_and_check(_chat_messages, user_id, CHAT_MAX, CHAT_WINDOW)


def get_chat_rate_status(user_id: str) -> dict:
    """Get current chat rate status without recording an action."""
    remaining, is_limited, retry_after = _get_remaining(
        _chat_messages, user_id, CHAT_MAX, CHAT_WINDOW
    )
    return {
        "remaining": remaining,
        "is_limited": is_limited,
        "retry_after": retry_after,
    }
