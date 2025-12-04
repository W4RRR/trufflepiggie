"""
Authentication manager for GitHub API token handling and rotation.
Implements intelligent token rotation based on rate limit status.

GitHub Rate Limits for Search API (critical for this tool):
- Authenticated: 30 requests/minute per user
- Unauthenticated: 10 requests/minute per IP

IMPORTANT: Rate limits are per USER, not per token!
Multiple tokens from same user share the same quota.

Reference: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
"""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import cycle
from pathlib import Path
from typing import Iterator, List, Optional

import requests

from ..utils import logger
from ..utils.helpers import mask_token


@dataclass
class TokenInfo:
    """
    Information about a GitHub API token.
    
    GitHub exposes rate limit info via headers:
    - x-ratelimit-limit: 30 (for search API)
    - x-ratelimit-remaining: requests left
    - x-ratelimit-reset: Unix timestamp for reset
    - x-ratelimit-resource: "search" or "core"
    
    Attributes:
        token: The actual token string.
        remaining: Remaining requests for search API (30/min max).
        reset_time: Unix timestamp when rate limit resets.
        is_valid: Whether the token is valid.
        resource: API resource type being tracked.
    """
    token: str
    remaining: int = 30  # GitHub search API limit per minute
    reset_time: int = 0
    is_valid: bool = True
    resource: str = "search"
    retry_after: Optional[int] = None
    
    @property
    def masked(self) -> str:
        """Get masked version of token."""
        return mask_token(self.token)
    
    @property
    def reset_datetime(self) -> datetime:
        """Get reset time as datetime."""
        if self.reset_time:
            return datetime.fromtimestamp(self.reset_time)
        return datetime.now()
    
    @property
    def seconds_until_reset(self) -> int:
        """Get seconds until rate limit resets."""
        return max(0, self.reset_time - int(time.time()))


class AuthManager:
    """
    Manages GitHub API tokens with automatic rotation and rate limit handling.
    
    Implements a round-robin rotation strategy with intelligent switching
    when tokens are exhausted. Monitors the SEARCH API rate limit specifically,
    not the core API limit (which is much higher but irrelevant for searches).
    
    CRITICAL: The Search API has a limit of 30 requests/minute (authenticated).
    This is separate from the Core API limit of 5,000/hour.
    
    Strategy:
    1. Monitor x-ratelimit-remaining proactively (don't wait for 403)
    2. Switch tokens when remaining < threshold
    3. If all tokens exhausted, wait for minimum reset time
    4. Respect Retry-After header on errors
    
    Attributes:
        tokens: List of TokenInfo objects.
        token_cycle: Cycle iterator for round-robin rotation.
        current_token: Currently active token.
        api_base: GitHub API base URL.
    """
    
    MIN_REMAINING_THRESHOLD = 2  # Switch token when remaining < this
    SEARCH_LIMIT_PER_MINUTE = 30  # GitHub Search API limit
    
    def __init__(
        self,
        tokens_dir: Optional[Path] = None,
        api_base: str = "https://api.github.com",
    ):
        """
        Initialize the authentication manager.
        
        Args:
            tokens_dir: Directory containing token files.
            api_base: GitHub API base URL.
            
        Raises:
            ValueError: If no valid tokens are found.
        """
        self.api_base = api_base
        self.tokens: List[TokenInfo] = []
        self._token_cycle: Optional[Iterator[TokenInfo]] = None
        self._current_token: Optional[TokenInfo] = None
        
        # Load tokens
        if tokens_dir is None:
            tokens_dir = Path(__file__).parent.parent.parent / "config" / "tokens"
        
        self._load_tokens(tokens_dir)
        
        if not self.tokens:
            raise ValueError(
                "No GitHub tokens found!\n"
                "Please add your tokens to: config/tokens/\n"
                "Create a .txt file with one token per line.\n"
                "Tokens should start with 'ghp_' or 'github_pat_'"
            )
        
        # Initialize rotation
        self._token_cycle = cycle(self.tokens)
        self._current_token = next(self._token_cycle)
        
        logger.info(f"Loaded {len(self.tokens)} GitHub token(s)")
    
    def _load_tokens(self, tokens_dir: Path) -> None:
        """
        Load tokens from all .txt files in the tokens directory.
        
        Args:
            tokens_dir: Directory to search for token files.
        """
        if not tokens_dir.exists():
            logger.warning(f"Tokens directory not found: {tokens_dir}")
            return
        
        # Token patterns
        token_pattern = re.compile(r'^(ghp_[a-zA-Z0-9]{36,}|github_pat_[a-zA-Z0-9_]{22,})$')
        
        for token_file in tokens_dir.glob("*.txt"):
            if token_file.name == ".keep":
                continue
                
            try:
                with open(token_file, "r", encoding="utf-8") as f:
                    for line in f:
                        token = line.strip()
                        if token and token_pattern.match(token):
                            self.tokens.append(TokenInfo(token=token))
                        elif token and not token.startswith("#"):
                            # Log invalid tokens (but not comments)
                            logger.warning(f"Invalid token format in {token_file.name}")
            except Exception as e:
                logger.error(f"Error reading {token_file}: {e}")
    
    @property
    def current_token(self) -> TokenInfo:
        """Get the current active token."""
        if self._current_token is None:
            raise ValueError("No token available")
        return self._current_token
    
    def get_auth_header(self) -> dict[str, str]:
        """
        Get the authorization header for API requests.
        
        Returns:
            Dictionary with Authorization header.
        """
        return {"Authorization": f"Bearer {self.current_token.token}"}
    
    def check_rate_limit(self) -> None:
        """
        Check and update rate limit status for current token.
        
        Makes a request to GitHub's rate_limit endpoint to get
        current status of the SEARCH API rate limit specifically.
        
        IMPORTANT: We check the "search" resource, not "core"!
        - search: 30 requests/minute (what we need)
        - core: 5,000 requests/hour (not relevant for searches)
        
        The /rate_limit endpoint itself doesn't count against limits.
        """
        try:
            response = requests.get(
                f"{self.api_base}/rate_limit",
                headers=self.get_auth_header(),
                timeout=10,
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # CRITICAL: Check the "search" resource specifically!
                # Don't be fooled by the higher "core" limits
                search_limit = data.get("resources", {}).get("search", {})
                
                self._current_token.remaining = search_limit.get("remaining", 0)
                self._current_token.reset_time = search_limit.get("reset", 0)
                self._current_token.resource = "search"
                self._current_token.is_valid = True
                
                logger.info(
                    f"Token {self.current_token.masked}: "
                    f"{self._current_token.remaining}/30 search requests remaining"
                )
                
            elif response.status_code == 401:
                logger.error(f"Token {self.current_token.masked} is invalid")
                self._current_token.is_valid = False
                self._rotate_token()
                
        except requests.RequestException as e:
            logger.warning(f"Failed to check rate limit: {e}")
    
    def update_from_response(self, response: requests.Response) -> None:
        """
        Update rate limit info from response headers.
        
        CRITICAL: Always monitor these headers proactively!
        Don't wait for 403 errors - check remaining BEFORE it hits 0.
        
        Headers to monitor:
        - X-RateLimit-Remaining: Requests left (MOST IMPORTANT)
        - X-RateLimit-Reset: When limit resets
        - X-RateLimit-Resource: "search" or "core"
        - Retry-After: Seconds to wait (on errors)
        
        Args:
            response: Response object from GitHub API.
        """
        try:
            headers = response.headers
            
            remaining = headers.get("X-RateLimit-Remaining")
            reset_time = headers.get("X-RateLimit-Reset")
            resource = headers.get("X-RateLimit-Resource")
            retry_after = headers.get("Retry-After")
            
            if remaining is not None:
                self._current_token.remaining = int(remaining)
            if reset_time is not None:
                self._current_token.reset_time = int(reset_time)
            if resource is not None:
                self._current_token.resource = resource
            if retry_after is not None:
                self._current_token.retry_after = int(retry_after)
            else:
                self._current_token.retry_after = None
                
        except (ValueError, TypeError):
            pass
    
    def _rotate_token(self) -> None:
        """Rotate to the next token in the pool."""
        if self._token_cycle is None:
            return
            
        # Try to find a token with remaining requests
        attempts = 0
        while attempts < len(self.tokens):
            self._current_token = next(self._token_cycle)
            if self._current_token.is_valid and self._current_token.remaining >= self.MIN_REMAINING_THRESHOLD:
                logger.info(f"Switched to token: {self.current_token.masked}")
                return
            attempts += 1
        
        # All tokens exhausted - need to wait
        logger.warning("All tokens exhausted!")
    
    def get_best_token(self) -> TokenInfo:
        """
        Get the best available token based on rate limit status.
        
        Checks current token status and rotates if necessary.
        If all tokens are exhausted, waits for reset.
        
        Returns:
            The best available token.
        """
        # Check if current token needs rotation
        if self._current_token.remaining < self.MIN_REMAINING_THRESHOLD:
            self._try_rotate_or_wait()
        
        return self.current_token
    
    def _try_rotate_or_wait(self) -> None:
        """
        Try to rotate to a valid token, or wait if all exhausted.
        """
        # Find any token with remaining requests
        for token in self.tokens:
            if token.is_valid and token.remaining >= self.MIN_REMAINING_THRESHOLD:
                while self._current_token != token:
                    self._current_token = next(self._token_cycle)
                logger.info(f"Switched to token: {self.current_token.masked}")
                return
        
        # All tokens exhausted - find minimum reset time
        valid_tokens = [t for t in self.tokens if t.is_valid]
        if not valid_tokens:
            raise ValueError("No valid tokens remaining!")
        
        min_reset = min(t.seconds_until_reset for t in valid_tokens)
        
        if min_reset > 0:
            logger.warning(f"All tokens exhausted. Waiting {min_reset}s for reset...")
            logger.countdown(min_reset + 5, "Waiting for rate limit reset")
            
            # Refresh rate limits after waiting
            for token in self.tokens:
                token.remaining = 30  # Reset to default
    
    def handle_rate_limit_error(self, response: requests.Response) -> bool:
        """
        Handle a rate limit error response (403 or 429).
        
        GitHub's recommended handling:
        1. If Retry-After header present, wait EXACTLY that time
        2. If no Retry-After, wait at least 60 seconds
        3. Use exponential backoff on repeated failures
        
        WARNING: Ignoring Retry-After can escalate to longer bans!
        
        Args:
            response: Response with rate limit error.
            
        Returns:
            True if handled and can retry, False otherwise.
        """
        self.update_from_response(response)
        
        # Check for Retry-After header (MUST respect this!)
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            wait_time = int(retry_after)
            logger.warning(f"Rate limited. Retry-After: {wait_time}s (respecting header)")
            logger.countdown(wait_time, "Waiting for Retry-After")
            return True
        
        # Check for abuse detection (secondary limits)
        response_text = response.text.lower()
        if "abuse" in response_text or "secondary" in response_text:
            logger.warning(
                "Secondary rate limit (abuse detection) triggered!\n"
                "This happens when:\n"
                "  - Too many concurrent requests\n"
                "  - Requests too fast to same endpoint\n"
                "  - Rapid-fire bursting\n"
                "Sleeping 60s and switching token..."
            )
            time.sleep(60)
            self._rotate_token()
            return True
        
        # Regular rate limit exhaustion
        self._current_token.remaining = 0
        logger.warning(
            f"Primary rate limit exhausted for token {self.current_token.masked}"
        )
        self._try_rotate_or_wait()
        return True
    
    def display_status(self) -> None:
        """Display current token status."""
        logger.token_status(
            token_id=self.current_token.masked,
            remaining=self.current_token.remaining,
            reset_time=self.current_token.reset_datetime.strftime("%H:%M:%S"),
        )

