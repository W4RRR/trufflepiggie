"""
Rate limiter implementation using token bucket algorithm.
Coordinates with AuthManager for intelligent request throttling.

GitHub Rate Limits (from official documentation):
- Search API Authenticated: 30 requests/minute
- Search API Unauthenticated: 10 requests/minute  
- REST Core Authenticated: 5,000 requests/hour
- REST Core Unauthenticated: 60 requests/hour

Reference: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..utils import logger


@dataclass
class RateLimitState:
    """
    Current rate limit state information.
    
    GitHub exposes this via HTTP headers:
    - x-ratelimit-limit: Max requests in window
    - x-ratelimit-remaining: Requests left
    - x-ratelimit-reset: Unix timestamp for reset
    - x-ratelimit-used: Requests consumed
    
    Attributes:
        remaining: Remaining requests.
        limit: Maximum requests per window.
        reset_time: Unix timestamp for reset.
        used: Requests used in current window.
        resource: API resource type (search/core).
    """
    remaining: int = 30
    limit: int = 30
    reset_time: int = 0
    used: int = 0
    resource: str = "search"
    retry_after: Optional[int] = None
    
    @property
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining <= 0
    
    @property
    def seconds_until_reset(self) -> int:
        """Get seconds until rate limit resets."""
        return max(0, self.reset_time - int(time.time()))
    
    @property
    def reset_datetime(self) -> datetime:
        """Get reset time as datetime."""
        if self.reset_time:
            return datetime.fromtimestamp(self.reset_time)
        return datetime.now()


class RateLimiter:
    """
    Rate limiter for GitHub API requests.
    
    Implements proactive rate limit monitoring as recommended by GitHub:
    - Monitor x-ratelimit-remaining BEFORE hitting limits
    - Respect Retry-After header on 403/429 errors
    - Use exponential backoff when no Retry-After provided
    
    Critical: GitHub Search API has MUCH stricter limits than Core API!
    - Search: 30 req/min (authenticated)
    - Core: 5,000 req/hour (authenticated)
    
    Attributes:
        state: Current rate limit state.
        min_remaining: Minimum remaining before pausing.
    """
    
    # GitHub API Rate Limits (official documentation)
    # Search API - per MINUTE (very restrictive!)
    SEARCH_LIMIT_AUTHENTICATED = 30      # per minute
    SEARCH_LIMIT_UNAUTHENTICATED = 10    # per minute
    SEARCH_WINDOW = 60                    # seconds
    
    # Core API - per HOUR
    CORE_LIMIT_AUTHENTICATED = 5000      # per hour
    CORE_LIMIT_UNAUTHENTICATED = 60      # per hour
    CORE_WINDOW = 3600                    # seconds
    
    # Enterprise limits
    ENTERPRISE_CORE_LIMIT = 15000        # per hour
    
    # Secondary limits (abuse detection)
    MAX_CONCURRENT_REQUESTS = 100
    BURST_LIMIT_REST = 900               # points per minute (unofficial)
    
    def __init__(self, min_remaining: int = 2, backoff_base: int = 60):
        """
        Initialize the rate limiter.
        
        Args:
            min_remaining: Minimum remaining requests before triggering wait.
            backoff_base: Base seconds for exponential backoff.
        """
        self.state = RateLimitState()
        self.min_remaining = min_remaining
        self.backoff_base = backoff_base
        self._last_request_time: float = 0
        self._consecutive_errors: int = 0
    
    def update_from_headers(self, headers: dict) -> None:
        """
        Update rate limit state from response headers.
        
        CRITICAL: Always monitor these headers proactively!
        Don't wait for 403 errors to check limits.
        
        Args:
            headers: Response headers dictionary.
        """
        try:
            # Standard rate limit headers
            if "X-RateLimit-Remaining" in headers:
                self.state.remaining = int(headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Limit" in headers:
                self.state.limit = int(headers["X-RateLimit-Limit"])
            if "X-RateLimit-Reset" in headers:
                self.state.reset_time = int(headers["X-RateLimit-Reset"])
            if "X-RateLimit-Used" in headers:
                self.state.used = int(headers["X-RateLimit-Used"])
            if "X-RateLimit-Resource" in headers:
                self.state.resource = headers["X-RateLimit-Resource"]
            
            # Retry-After header (critical for 403/429 responses)
            if "Retry-After" in headers:
                self.state.retry_after = int(headers["Retry-After"])
            else:
                self.state.retry_after = None
                
            # Reset error counter on successful header parse
            self._consecutive_errors = 0
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing rate limit headers: {e}")
    
    def check_and_wait(self) -> bool:
        """
        Proactively check rate limit and wait if necessary.
        
        This should be called BEFORE making requests, not after!
        Following GitHub's best practices for rate limit handling.
        
        Returns:
            True if can proceed, False if should abort.
        """
        # If we have a Retry-After from previous error, respect it
        if self.state.retry_after:
            logger.warning(
                f"Retry-After header present. Waiting {self.state.retry_after}s..."
            )
            logger.countdown(self.state.retry_after, "Retry-After cooldown")
            self.state.retry_after = None
            return True
        
        # Proactive check: don't wait until remaining = 0
        if self.state.remaining <= self.min_remaining:
            wait_time = self.state.seconds_until_reset
            if wait_time > 0:
                logger.warning(
                    f"Rate limit low ({self.state.remaining} remaining). "
                    f"Waiting {wait_time}s until reset..."
                )
                logger.countdown(wait_time + 2, "Rate limit cooldown")
                # Reset state after waiting
                self.state.remaining = self.state.limit
            return True
        
        return True
    
    def handle_rate_limit_response(self, status_code: int, headers: dict) -> int:
        """
        Handle a rate limit error response (403 or 429).
        
        Implements GitHub's recommended retry strategy:
        1. If Retry-After header present, wait exactly that time
        2. Otherwise, use exponential backoff starting at 60s
        
        Args:
            status_code: HTTP status code (403 or 429).
            headers: Response headers.
            
        Returns:
            Seconds to wait before retry.
        """
        self._consecutive_errors += 1
        
        # Check for Retry-After header (must respect this!)
        retry_after = headers.get("Retry-After")
        if retry_after:
            wait_time = int(retry_after)
            logger.warning(f"Rate limited. Retry-After: {wait_time}s")
            return wait_time
        
        # No Retry-After: use exponential backoff
        # Base: 60s, then 120s, 240s, etc.
        wait_time = self.backoff_base * (2 ** (self._consecutive_errors - 1))
        wait_time = min(wait_time, 3600)  # Cap at 1 hour
        
        logger.warning(
            f"Rate limited (no Retry-After). "
            f"Exponential backoff: {wait_time}s (attempt {self._consecutive_errors})"
        )
        return wait_time
    
    def can_make_request(self) -> bool:
        """
        Check if a request can be made without waiting.
        
        Returns:
            True if request can proceed immediately.
        """
        return self.state.remaining > self.min_remaining
    
    def record_request(self) -> None:
        """Record that a request was made."""
        self._last_request_time = time.time()
        if self.state.remaining > 0:
            self.state.remaining -= 1
            self.state.used += 1
    
    def get_status_string(self) -> str:
        """
        Get a formatted status string.
        
        Returns:
            Formatted rate limit status.
        """
        reset_str = self.state.reset_datetime.strftime("%H:%M:%S")
        return (
            f"[{self.state.resource.upper()}] "
            f"Remaining: {self.state.remaining}/{self.state.limit} | "
            f"Reset: {reset_str}"
        )
    
    def get_optimal_delay(self) -> float:
        """
        Calculate optimal delay to stay within rate limits.
        
        For Search API (30 req/min), optimal is ~2s between requests.
        Adding jitter helps avoid synchronized request patterns.
        
        Returns:
            Recommended delay in seconds.
        """
        if self.state.resource == "search":
            # 30 requests per 60 seconds = 1 request per 2 seconds
            base_delay = self.SEARCH_WINDOW / self.SEARCH_LIMIT_AUTHENTICATED
        else:
            # Core API is much more lenient
            base_delay = 0.5
        
        return base_delay

