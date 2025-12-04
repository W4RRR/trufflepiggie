"""
Helper utilities and common functions.
"""

import re
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


@dataclass
class SearchResult:
    """
    Represents a single search result from GitHub.
    
    Attributes:
        type: Result type (repo/gist).
        name: Repository or Gist name.
        url: Full URL to the resource.
        html_url: Browser-viewable URL.
        owner: Owner username.
        created_at: Creation date.
        updated_at: Last update date.
        description: Repository/Gist description.
        language: Primary language.
        stars: Star count (repos only).
        raw_data: Original API response data.
    """
    type: str
    name: str
    url: str
    html_url: str
    owner: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "name": self.name,
            "url": self.url,
            "html_url": self.html_url,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "description": self.description,
            "language": self.language,
            "stars": self.stars,
        }
    
    def to_trufflehog_target(self) -> str:
        """Get the URL/target for TruffleHog scanning."""
        return self.html_url


@dataclass
class ScanState:
    """
    Maintains the current scan state for graceful shutdown.
    
    Attributes:
        results: Set of unique result URLs (for deduplication).
        total_repos: Count of repositories found.
        total_gists: Count of gists found.
        current_slice: Current time slice being processed.
        start_time: Scan start timestamp.
    """
    results: Set[str] = field(default_factory=set)
    total_repos: int = 0
    total_gists: int = 0
    current_slice: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    interrupted: bool = False
    
    def add_result(self, result: SearchResult) -> bool:
        """
        Add a result if not duplicate.
        
        Args:
            result: Search result to add.
            
        Returns:
            True if added (new), False if duplicate.
        """
        if result.url in self.results:
            return False
        
        self.results.add(result.url)
        if result.type == "repository":
            self.total_repos += 1
        else:
            self.total_gists += 1
        return True
    
    def get_duration(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file.
        
    Returns:
        Configuration dictionary.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    
    default_config = {
        "app": {"name": "TrufflePiggie", "version": "1.0.0"},
        "network": {
            "min_delay": 2.0,
            "max_delay": 5.5,
            "max_retries": 3,
            "timeout": 15,
            "abuse_sleep": 60,
        },
        "search": {
            "per_page": 100,
            "max_depth": "day",
            "default_years": "2015-2024",
        },
        "github": {
            "api_base": "https://api.github.com",
            "search_code_endpoint": "/search/code",
            "search_repos_endpoint": "/search/repositories",
            "rate_limit_endpoint": "/rate_limit",
        },
        "output": {
            "default_format": "json",
        },
    }
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            # Merge with defaults
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if subkey not in config[key]:
                            config[key][subkey] = subvalue
            return config
    except FileNotFoundError:
        return default_config
    except yaml.YAMLError as e:
        print(f"Error parsing config: {e}")
        return default_config


def parse_year_range(year_str: str) -> tuple[int, int]:
    """
    Parse year range string.
    
    Args:
        year_str: Year range (e.g., "2020-2024" or "2023").
        
    Returns:
        Tuple of (start_year, end_year).
    """
    if "-" in year_str:
        parts = year_str.split("-")
        return int(parts[0]), int(parts[1])
    else:
        year = int(year_str)
        return year, year


def validate_domain(domain: str) -> str:
    """
    Validate and clean domain input.
    
    Args:
        domain: Domain string to validate.
        
    Returns:
        Cleaned domain string.
        
    Raises:
        ValueError: If domain is invalid.
    """
    # Remove protocol if present
    domain = re.sub(r'^https?://', '', domain)
    # Remove trailing slashes
    domain = domain.rstrip('/')
    # Remove paths
    domain = domain.split('/')[0]
    
    # Basic validation
    if not domain or len(domain) < 3:
        raise ValueError(f"Invalid domain: {domain}")
    
    return domain


def mask_token(token: str) -> str:
    """
    Mask a token for display, showing only first and last 4 chars.
    
    Args:
        token: Full token string.
        
    Returns:
        Masked token string.
    """
    if len(token) <= 12:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


def setup_signal_handlers(state: ScanState) -> None:
    """
    Setup graceful shutdown handlers for Ctrl+C.
    
    Args:
        state: Scan state to preserve on shutdown.
    """
    def signal_handler(signum: int, frame: Any) -> None:
        from . import logger
        logger.warning("\nInterrupt received! Saving current progress...")
        state.interrupted = True
    
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)


def format_date_range(start_date: str, end_date: str) -> str:
    """
    Format a date range for GitHub search query.
    
    Args:
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        
    Returns:
        Formatted date range string.
    """
    return f"{start_date}..{end_date}"


def get_months_in_year(year: int) -> List[tuple[str, str]]:
    """
    Get all month ranges for a given year.
    
    Args:
        year: Year to split into months.
        
    Returns:
        List of (start_date, end_date) tuples for each month.
    """
    months = []
    for month in range(1, 13):
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year}-12-31"
        else:
            # Last day of current month
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            end = f"{year}-{month:02d}-{last_day:02d}"
        months.append((start, end))
    return months


def get_days_in_month(year: int, month: int) -> List[tuple[str, str]]:
    """
    Get all day ranges for a given month.
    
    Args:
        year: Year.
        month: Month (1-12).
        
    Returns:
        List of (start_date, end_date) tuples for each day.
    """
    import calendar
    days = []
    last_day = calendar.monthrange(year, month)[1]
    
    for day in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        days.append((date_str, date_str))
    
    return days

