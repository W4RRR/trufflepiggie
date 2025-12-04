"""
Main search engine with Recursive Time Slicing algorithm.
Implements intelligent date-range splitting to bypass GitHub's 1000 result limit.
"""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple
from urllib.parse import quote

from ..managers.auth_manager import AuthManager
from ..managers.output_manager import OutputManager
from ..utils import logger
from ..utils.helpers import (
    SearchResult,
    ScanState,
    get_days_in_month,
    get_months_in_year,
)
from ..utils.http_client import HttpClient
from .rate_limiter import RateLimiter


@dataclass
class TimeSlice:
    """
    Represents a time slice for recursive searching.
    
    Attributes:
        start_date: Start of the slice (YYYY-MM-DD).
        end_date: End of the slice (YYYY-MM-DD).
        level: Depth level (year/month/day).
    """
    start_date: str
    end_date: str
    level: str = "year"
    
    def __str__(self) -> str:
        return f"{self.start_date}..{self.end_date}"


class SearchEngine:
    """
    GitHub search engine with Recursive Time Slicing.
    
    The engine recursively splits time ranges when result count exceeds
    GitHub's 1000 result limit. Goes from years -> months -> days.
    
    Attributes:
        auth: Authentication manager.
        http: HTTP client.
        rate_limiter: Rate limit handler.
        output: Output manager.
        state: Current scan state.
        config: Configuration dictionary.
    """
    
    GITHUB_MAX_RESULTS = 1000
    MAX_PER_PAGE = 100
    
    def __init__(
        self,
        auth_manager: AuthManager,
        http_client: HttpClient,
        output_manager: OutputManager,
        config: Dict[str, Any],
    ):
        """
        Initialize the search engine.
        
        Args:
            auth_manager: Token manager.
            http_client: HTTP client.
            output_manager: Output handler.
            config: Configuration dictionary.
        """
        self.auth = auth_manager
        self.http = http_client
        self.output = output_manager
        self.config = config
        self.rate_limiter = RateLimiter()
        self.state = ScanState()
        
        self.api_base = config.get("github", {}).get("api_base", "https://api.github.com")
        self.per_page = config.get("search", {}).get("per_page", 100)
        self.abuse_sleep = config.get("network", {}).get("abuse_sleep", 60)
    
    def search_domain(
        self,
        domain: str,
        start_year: int,
        end_year: int,
        search_repos: bool = True,
        search_gists: bool = True,
    ) -> ScanState:
        """
        Search for a domain across GitHub repositories and gists.
        
        Args:
            domain: Target domain to search for.
            start_year: Start year for search range.
            end_year: End year for search range.
            search_repos: Whether to search repositories.
            search_gists: Whether to search gists.
            
        Returns:
            Final scan state with results.
        """
        logger.info(f"Starting search for: {domain}")
        logger.info(f"Year range: {start_year} - {end_year}")
        
        # Generate initial time slices (one per year)
        slices = self._generate_year_slices(start_year, end_year)
        
        progress = logger.create_progress()
        
        with progress:
            overall_task = progress.add_task(
                f"[cyan]Scanning {domain}",
                total=len(slices),
            )
            
            for time_slice in slices:
                if self.state.interrupted:
                    logger.warning("Scan interrupted by user")
                    break
                
                self.state.current_slice = str(time_slice)
                
                # Search repositories
                if search_repos:
                    progress.update(
                        overall_task,
                        description=f"[cyan]Repos: {time_slice}",
                    )
                    self._recursive_search(
                        domain=domain,
                        time_slice=time_slice,
                        search_type="repositories",
                        progress=progress,
                    )
                
                # Search code (which includes gists in results)
                if search_gists:
                    progress.update(
                        overall_task,
                        description=f"[magenta]Code: {time_slice}",
                    )
                    self._recursive_search(
                        domain=domain,
                        time_slice=time_slice,
                        search_type="code",
                        progress=progress,
                    )
                
                progress.update(overall_task, advance=1)
        
        return self.state
    
    def _generate_year_slices(self, start: int, end: int) -> List[TimeSlice]:
        """
        Generate time slices for each year in range.
        
        Args:
            start: Start year.
            end: End year.
            
        Returns:
            List of TimeSlice objects.
        """
        slices = []
        for year in range(start, end + 1):
            slices.append(TimeSlice(
                start_date=f"{year}-01-01",
                end_date=f"{year}-12-31",
                level="year",
            ))
        return slices
    
    def _recursive_search(
        self,
        domain: str,
        time_slice: TimeSlice,
        search_type: str,
        progress: Any,
        depth: int = 0,
    ) -> None:
        """
        Recursively search with time slicing.
        
        If result count exceeds 1000, splits the time range and recurses.
        
        Args:
            domain: Target domain.
            time_slice: Current time slice.
            search_type: Type of search (repositories/code).
            progress: Progress bar instance.
            depth: Current recursion depth.
        """
        if self.state.interrupted:
            return
        
        # First, get result count for this slice
        count = self._get_result_count(domain, time_slice, search_type)
        
        if count == 0:
            logger.info(f"No results for {time_slice} ({search_type})")
            return
        
        logger.info(f"Found {count} results for {time_slice} ({search_type})")
        
        if count <= self.GITHUB_MAX_RESULTS:
            # Can fetch all results directly
            self._fetch_all_pages(domain, time_slice, search_type, progress)
        else:
            # Need to split time range
            logger.warning(
                f"Results exceed 1000 for {time_slice}, splitting..."
            )
            sub_slices = self._split_time_slice(time_slice)
            
            if not sub_slices:
                # Already at day level, fetch what we can
                logger.warning(
                    f"At day level with {count} results. Fetching max 1000."
                )
                self._fetch_all_pages(domain, time_slice, search_type, progress)
                return
            
            for sub_slice in sub_slices:
                if self.state.interrupted:
                    return
                self._recursive_search(
                    domain, sub_slice, search_type, progress, depth + 1
                )
    
    def _split_time_slice(self, time_slice: TimeSlice) -> List[TimeSlice]:
        """
        Split a time slice into smaller chunks.
        
        Years -> Months -> Days
        
        Args:
            time_slice: Time slice to split.
            
        Returns:
            List of smaller time slices.
        """
        if time_slice.level == "year":
            # Split into months
            year = int(time_slice.start_date[:4])
            months = get_months_in_year(year)
            return [
                TimeSlice(start, end, "month")
                for start, end in months
            ]
        
        elif time_slice.level == "month":
            # Split into days
            parts = time_slice.start_date.split("-")
            year = int(parts[0])
            month = int(parts[1])
            days = get_days_in_month(year, month)
            return [
                TimeSlice(start, end, "day")
                for start, end in days
            ]
        
        else:
            # Already at day level, cannot split further
            return []
    
    def _get_result_count(
        self,
        domain: str,
        time_slice: TimeSlice,
        search_type: str,
    ) -> int:
        """
        Get the total result count for a search query.
        
        Uses per_page=1 to minimize bandwidth.
        
        Args:
            domain: Target domain.
            time_slice: Time slice.
            search_type: Search type.
            
        Returns:
            Total result count.
        """
        query = self._build_query(domain, time_slice)
        endpoint = f"{self.api_base}/search/{search_type}"
        
        params = {
            "q": query,
            "per_page": 1,
            "page": 1,
        }
        
        response = self._make_request(endpoint, params)
        
        if response and response.status_code == 200:
            data = response.json()
            return data.get("total_count", 0)
        
        return 0
    
    def _fetch_all_pages(
        self,
        domain: str,
        time_slice: TimeSlice,
        search_type: str,
        progress: Any,
    ) -> None:
        """
        Fetch all pages of results for a time slice.
        
        Args:
            domain: Target domain.
            time_slice: Time slice.
            search_type: Search type.
            progress: Progress bar.
        """
        query = self._build_query(domain, time_slice)
        endpoint = f"{self.api_base}/search/{search_type}"
        
        page = 1
        max_pages = self.GITHUB_MAX_RESULTS // self.per_page
        
        while page <= max_pages:
            if self.state.interrupted:
                return
            
            params = {
                "q": query,
                "per_page": self.per_page,
                "page": page,
                "sort": "indexed",
                "order": "desc",
            }
            
            response = self._make_request(endpoint, params)
            
            if not response or response.status_code != 200:
                break
            
            data = response.json()
            items = data.get("items", [])
            
            if not items:
                break
            
            # Process results
            for item in items:
                result = self._parse_result(item, search_type)
                if result and self.state.add_result(result):
                    self.output.add_result(result)
            
            # Check if more pages
            total = data.get("total_count", 0)
            if page * self.per_page >= total or page * self.per_page >= self.GITHUB_MAX_RESULTS:
                break
            
            page += 1
    
    def _build_query(self, domain: str, time_slice: TimeSlice) -> str:
        """
        Build GitHub search query string.
        
        Args:
            domain: Target domain.
            time_slice: Time slice.
            
        Returns:
            Formatted query string.
        """
        # Quote the domain for exact match
        query = f'"{domain}"'
        
        # Add date range
        if time_slice.start_date == time_slice.end_date:
            query += f" created:{time_slice.start_date}"
        else:
            query += f" created:{time_slice.start_date}..{time_slice.end_date}"
        
        return query
    
    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
    ) -> Optional[Any]:
        """
        Make an API request with rate limit handling.
        
        Args:
            endpoint: API endpoint.
            params: Query parameters.
            
        Returns:
            Response object or None on failure.
        """
        # Ensure we have a valid token
        self.auth.get_best_token()
        
        # Check rate limit
        self.rate_limiter.check_and_wait()
        
        try:
            response = self.http.get(
                endpoint,
                headers=self.auth.get_auth_header(),
                params=params,
            )
            
            # Update rate limit info
            self.rate_limiter.update_from_headers(dict(response.headers))
            self.auth.update_from_response(response)
            
            # Handle rate limit errors
            if response.status_code == 403:
                if "rate limit" in response.text.lower():
                    logger.warning("Rate limit hit, rotating token...")
                    self.auth.handle_rate_limit_error(response)
                    return self._make_request(endpoint, params)  # Retry
                elif "abuse" in response.text.lower():
                    logger.warning("Abuse detection! Sleeping...")
                    time.sleep(self.abuse_sleep)
                    return self._make_request(endpoint, params)
            
            elif response.status_code == 422:
                # Validation error (e.g., query too long)
                logger.error(f"Validation error: {response.text}")
                return None
            
            return response
            
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def _parse_result(
        self,
        item: Dict[str, Any],
        search_type: str,
    ) -> Optional[SearchResult]:
        """
        Parse a search result item into SearchResult.
        
        Args:
            item: Raw API response item.
            search_type: Type of search.
            
        Returns:
            SearchResult or None if parsing fails.
        """
        try:
            if search_type == "repositories":
                return SearchResult(
                    type="repository",
                    name=item.get("full_name", item.get("name", "unknown")),
                    url=item.get("url", ""),
                    html_url=item.get("html_url", ""),
                    owner=item.get("owner", {}).get("login", "unknown"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    description=item.get("description"),
                    language=item.get("language"),
                    stars=item.get("stargazers_count", 0),
                    raw_data=item,
                )
            else:
                # Code search result
                repo = item.get("repository", {})
                return SearchResult(
                    type="code",
                    name=item.get("name", "unknown"),
                    url=item.get("url", ""),
                    html_url=item.get("html_url", ""),
                    owner=repo.get("owner", {}).get("login", "unknown"),
                    description=repo.get("description"),
                    language=item.get("language"),
                    raw_data=item,
                )
        except Exception as e:
            logger.warning(f"Failed to parse result: {e}")
            return None


class GistSearchEngine:
    """
    Separate engine for searching GitHub Gists.
    
    GitHub Gists have a different search mechanism and are accessed
    via gist.github.com rather than the main API.
    """
    
    GIST_SEARCH_URL = "https://gist.github.com/search"
    
    def __init__(
        self,
        http_client: HttpClient,
        output_manager: OutputManager,
        state: ScanState,
    ):
        """
        Initialize the gist search engine.
        
        Args:
            http_client: HTTP client.
            output_manager: Output handler.
            state: Shared scan state.
        """
        self.http = http_client
        self.output = output_manager
        self.state = state
    
    def search_gists(self, domain: str) -> int:
        """
        Search for gists containing a domain.
        
        Note: GitHub Gist search doesn't support API access,
        so this uses web scraping.
        
        Args:
            domain: Target domain.
            
        Returns:
            Number of gists found.
        """
        logger.info(f"Searching Gists for: {domain}")
        
        # Build search URL
        query = f'*."{domain}"'
        
        page = 1
        found = 0
        
        while page <= 10:  # Limit to first 10 pages
            if self.state.interrupted:
                break
            
            try:
                response = self.http.get(
                    self.GIST_SEARCH_URL,
                    params={"q": query, "p": page},
                )
                
                if response.status_code != 200:
                    break
                
                # Parse gist URLs from HTML
                gists = self._parse_gist_page(response.text)
                
                if not gists:
                    break
                
                for gist_url, gist_name, owner in gists:
                    result = SearchResult(
                        type="gist",
                        name=gist_name,
                        url=gist_url,
                        html_url=gist_url,
                        owner=owner,
                    )
                    if self.state.add_result(result):
                        self.output.add_result(result)
                        found += 1
                
                page += 1
                
            except Exception as e:
                logger.warning(f"Gist search error: {e}")
                break
        
        logger.info(f"Found {found} gists")
        return found
    
    def _parse_gist_page(self, html: str) -> List[Tuple[str, str, str]]:
        """
        Parse gist information from search results HTML.
        
        Args:
            html: Raw HTML content.
            
        Returns:
            List of (url, name, owner) tuples.
        """
        gists = []
        
        # Pattern to match gist links
        # Format: /username/gist_id
        pattern = r'href="(/[^/]+/[a-f0-9]{32})"'
        
        for match in re.finditer(pattern, html):
            path = match.group(1)
            parts = path.strip("/").split("/")
            if len(parts) == 2:
                owner = parts[0]
                gist_id = parts[1]
                url = f"https://gist.github.com{path}"
                gists.append((url, gist_id[:12], owner))
        
        return gists

