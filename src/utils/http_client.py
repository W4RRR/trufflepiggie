"""
Robust HTTP client with retry logic, jitter, and User-Agent rotation.
"""

import random
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import logger


class HttpClient:
    """
    HTTP client wrapper with retry logic, jitter delays, and User-Agent rotation.
    
    Attributes:
        session: Requests session for connection pooling.
        min_delay: Minimum delay between requests.
        max_delay: Maximum delay between requests.
        timeout: Request timeout in seconds.
        user_agents: List of User-Agent strings for rotation.
    """
    
    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 5.5,
        timeout: int = 15,
        max_retries: int = 3,
        user_agents_file: Optional[Path] = None,
    ):
        """
        Initialize the HTTP client.
        
        Args:
            min_delay: Minimum delay between requests (seconds).
            max_delay: Maximum delay between requests (seconds).
            timeout: Request timeout (seconds).
            max_retries: Maximum retry attempts.
            user_agents_file: Path to User-Agents file.
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self._fixed_delay: Optional[float] = None
        self._delay_range: Optional[Tuple[float, float]] = None
        
        # Load User-Agents
        self.user_agents = self._load_user_agents(user_agents_file)
        
        # Create session with retry strategy
        self.session = self._create_session()
    
    def _load_user_agents(self, file_path: Optional[Path] = None) -> list[str]:
        """
        Load User-Agents from file.
        
        Args:
            file_path: Path to User-Agents file.
            
        Returns:
            List of User-Agent strings.
        """
        if file_path is None:
            file_path = Path(__file__).parent.parent.parent / "user_agents.txt"
        
        default_ua = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ]
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                agents = [line.strip() for line in f if line.strip()]
                return agents if agents else default_ua
        except FileNotFoundError:
            logger.warning(f"User-Agents file not found: {file_path}")
            return default_ua
    
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry strategy.
        
        Returns:
            Configured requests Session.
        """
        session = requests.Session()
        
        # Retry strategy for 5xx errors
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def set_delay(self, delay_str: str) -> None:
        """
        Set the delay configuration from string.
        
        Args:
            delay_str: Delay string (e.g., "2.5" for fixed or "1.5-3.5" for range).
        """
        if "-" in delay_str:
            parts = delay_str.split("-")
            if len(parts) == 2:
                try:
                    self._delay_range = (float(parts[0]), float(parts[1]))
                    self._fixed_delay = None
                    logger.info(f"Delay set to random range: {self._delay_range[0]}-{self._delay_range[1]}s")
                except ValueError:
                    logger.warning(f"Invalid delay range: {delay_str}, using defaults")
        else:
            try:
                self._fixed_delay = float(delay_str)
                self._delay_range = None
                logger.info(f"Delay set to fixed: {self._fixed_delay}s")
            except ValueError:
                logger.warning(f"Invalid delay value: {delay_str}, using defaults")
    
    def _get_delay(self) -> float:
        """
        Get the delay to apply before next request.
        
        Returns:
            Delay in seconds.
        """
        if self._fixed_delay is not None:
            return self._fixed_delay
        elif self._delay_range is not None:
            return random.uniform(self._delay_range[0], self._delay_range[1])
        else:
            return random.uniform(self.min_delay, self.max_delay)
    
    def _get_random_user_agent(self) -> str:
        """
        Get a random User-Agent from the pool.
        
        Returns:
            Random User-Agent string.
        """
        return random.choice(self.user_agents)
    
    def _apply_jitter(self) -> None:
        """Apply random delay between requests."""
        delay = self._get_delay()
        time.sleep(delay)
    
    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        apply_jitter: bool = True,
    ) -> requests.Response:
        """
        Perform a GET request with jitter and User-Agent rotation.
        
        Args:
            url: Target URL.
            headers: Additional headers.
            params: Query parameters.
            apply_jitter: Whether to apply delay before request.
            
        Returns:
            Response object.
            
        Raises:
            requests.RequestException: On request failure after retries.
        """
        if apply_jitter:
            self._apply_jitter()
        
        # Merge headers with random User-Agent
        request_headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "application/vnd.github.v3+json",
        }
        if headers:
            request_headers.update(headers)
        
        try:
            response = self.session.get(
                url,
                headers=request_headers,
                params=params,
                timeout=self.timeout,
            )
            return response
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def close(self) -> None:
        """Close the session."""
        self.session.close()

