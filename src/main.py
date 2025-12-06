#!/usr/bin/env python3
"""
TrufflePiggie - GitHub OSINT Tool for Secret Discovery

A tool to find GitHub repositories and gists related to a domain,
designed to work with TruffleHog for credential scanning.

Author: @W4R
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.engine import GistSearchEngine, SearchEngine
from src.managers.auth_manager import AuthManager
from src.managers.output_manager import OutputManager
from src.utils import logger
from src.utils.helpers import (
    ScanState,
    load_config,
    parse_year_range,
    setup_signal_handlers,
    validate_domain,
)
from src.utils.http_client import HttpClient


def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser for CLI.
    
    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="trufflepiggie",
        description="🐷 TrufflePiggie - GitHub OSINT Tool for Secret Discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py -q example.com -o results.json
  python main.py -q example.com -y 2020-2024 -f html
  python main.py -l subdomains.txt -D 1.5-3.5 -f all
  python main.py -q password --gists-only -o secrets.txt -f txt

Rate Limit Info:
  GitHub Search API: 30 requests/minute (authenticated)
  Use multiple tokens in config/tokens/ for rotation.

For more info: https://github.com/trufflesecurity/trufflehog
        """,
    )
    
    # Query arguments (one required)
    parser.add_argument(
        "-q", "--query",
        type=str,
        required=False,
        help="Domain or search query (e.g., example.com, filename:password)",
    )
    
    parser.add_argument(
        "-l", "--list",
        type=str,
        required=False,
        help="File containing list of domains/subdomains (one per line)",
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="results",
        help="Output file path (without extension). Default: 'results'",
    )
    
    parser.add_argument(
        "-f", "--format",
        type=str,
        choices=["txt", "json", "csv", "html", "all"],
        default="json",
        help="Output format. Default: json",
    )
    
    # Search options
    parser.add_argument(
        "-y", "--years",
        type=str,
        default=None,
        help="Year range to search (e.g., '2020-2024' or '2023'). Default: 2015-current",
    )
    
    parser.add_argument(
        "--repos-only",
        action="store_true",
        help="Search only repositories (skip gists)",
    )
    
    parser.add_argument(
        "--gists-only",
        action="store_true",
        help="Search only gists (skip repositories)",
    )
    
    parser.add_argument(
        "--code-only",
        action="store_true",
        help="Search only code (skip repository metadata search)",
    )
    
    # Delay options
    parser.add_argument(
        "-D", "--delay",
        type=str,
        default=None,
        help="Delay between requests. Fixed (e.g., '2.5') or range (e.g., '1.5-3.5')",
    )
    
    # Token options
    parser.add_argument(
        "-t", "--token",
        type=str,
        default=None,
        help="Single GitHub token (or use config/tokens/ for multiple)",
    )
    
    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Don't display ASCII art banner",
    )
    
    # TruffleHog integration
    parser.add_argument(
        "--trufflehog-list",
        action="store_true",
        help="Also export a simple URL list for TruffleHog",
    )
    
    return parser


def load_domains_from_file(filepath: str) -> list[str]:
    """
    Load domains from a file (one per line).
    
    Args:
        filepath: Path to file containing domains.
        
    Returns:
        List of domains.
    """
    domains = []
    path = Path(filepath)
    
    if not path.exists():
        raise FileNotFoundError(f"Domain list file not found: {filepath}")
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                domains.append(line)
    
    if not domains:
        raise ValueError(f"No valid domains found in: {filepath}")
    
    return domains


def main() -> int:
    """
    Main entry point for TrufflePiggie.
    
    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Display banner
    if not args.no_banner:
        logger.print_banner()
    
    # Load configuration
    config = load_config()
    
    # Validate that either -q or -l is provided
    if not args.query and not args.list:
        logger.error("You must provide either -q/--query or -l/--list")
        return 1
    
    if args.query and args.list:
        logger.error("Use either -q/--query or -l/--list, not both")
        return 1
    
    # Get list of domains to process
    try:
        if args.list:
            domains = load_domains_from_file(args.list)
            logger.info(f"Loaded [highlight]{len(domains)}[/highlight] domains from {args.list}")
        else:
            query = args.query.strip()
            if not query:
                logger.error("Query cannot be empty!")
                return 1
            domains = [query]
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except ValueError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Invalid query: {e}")
        return 1
    
    # Parse year range
    current_year = datetime.now().year
    if args.years:
        try:
            start_year, end_year = parse_year_range(args.years)
        except ValueError as e:
            logger.error(f"Invalid year range: {e}")
            return 1
    else:
        start_year = 2015
        end_year = current_year
    
    # Validate years
    if start_year > end_year:
        logger.error("Start year cannot be greater than end year!")
        return 1
    if end_year > current_year:
        end_year = current_year
        logger.warning(f"End year adjusted to current year: {end_year}")
    
    # Show targets
    if len(domains) == 1:
        logger.info(f"Target: [highlight]{domains[0]}[/highlight]")
    else:
        logger.info(f"Targets: [highlight]{len(domains)} domains[/highlight]")
    logger.info(f"Year range: {start_year} - {end_year}")
    logger.info(f"Output format: {args.format}")
    
    # Initialize HTTP client
    http_client = HttpClient(
        min_delay=config.get("network", {}).get("min_delay", 2.0),
        max_delay=config.get("network", {}).get("max_delay", 5.5),
        timeout=config.get("network", {}).get("timeout", 15),
        max_retries=config.get("network", {}).get("max_retries", 3),
    )
    
    # Set custom delay if provided
    if args.delay:
        http_client.set_delay(args.delay)
    
    # Initialize authentication
    try:
        if args.token:
            # Create temporary token file
            tokens_dir = Path(__file__).parent.parent / "config" / "tokens"
            tokens_dir.mkdir(parents=True, exist_ok=True)
            temp_token_file = tokens_dir / "_temp_token.txt"
            with open(temp_token_file, "w") as f:
                f.write(args.token)
            auth_manager = AuthManager(tokens_dir=tokens_dir)
        else:
            auth_manager = AuthManager()
    except ValueError as e:
        logger.error(str(e))
        logger.info("To get a GitHub token:")
        logger.info("  1. Go to https://github.com/settings/tokens")
        logger.info("  2. Generate new token (classic)")
        logger.info("  3. Select 'repo' and 'gist' scopes")
        logger.info("  4. Save to config/tokens/my_tokens.txt")
        return 1
    
    # Initialize output manager (use first domain or "multi" for multiple)
    output_domain = domains[0] if len(domains) == 1 else "multi-domain"
    output_manager = OutputManager(
        output_path=args.output,
        output_format=args.format,
        domain=output_domain,
    )
    
    # Create scan state and setup signal handlers
    state = ScanState()
    setup_signal_handlers(state)
    
    # Determine what to search
    search_repos = not args.gists_only and not args.code_only
    search_code = not args.repos_only
    search_gists = not args.repos_only and not args.code_only
    
    try:
        # Initialize search engine
        engine = SearchEngine(
            auth_manager=auth_manager,
            http_client=http_client,
            output_manager=output_manager,
            config=config,
        )
        engine.state = state
        
        # Process each domain
        for idx, domain in enumerate(domains):
            if state.interrupted:
                break
            
            # Show progress for multiple domains
            if len(domains) > 1:
                logger.info("")
                logger.highlight(f"[{idx + 1}/{len(domains)}] Scanning: {domain}")
            
            # Run main search for this domain
            state = engine.search_domain(
                domain=domain,
                start_year=start_year,
                end_year=end_year,
                search_repos=search_repos,
                search_gists=search_code,
            )
            
            # Search gists separately if requested
            if search_gists and not state.interrupted:
                gist_engine = GistSearchEngine(
                    http_client=http_client,
                    output_manager=output_manager,
                    state=state,
                )
                gist_engine.search_gists(domain)
            
            # Brief pause between domains to respect rate limits
            if len(domains) > 1 and idx < len(domains) - 1 and not state.interrupted:
                import time
                import random
                wait_time = random.uniform(2.0, 5.0)
                logger.info(f"Waiting {wait_time:.1f}s before next domain (rate limit protection)...")
                time.sleep(wait_time)
        
        # Finalize output
        output_files = output_manager.finalize(
            total_repos=state.total_repos,
            total_gists=state.total_gists,
        )
        
        # Export TruffleHog list if requested
        if args.trufflehog_list:
            output_manager.export_trufflehog_list()
        
        # Print statistics
        logger.print_stats(
            total_repos=state.total_repos,
            total_gists=state.total_gists,
            duration=state.get_duration(),
            output_file=str(output_files[0]) if output_files else None,
        )
        
        if state.interrupted:
            logger.warning("Scan was interrupted. Partial results saved.")
        else:
            logger.success("Scan completed successfully!")
        
        # Suggest TruffleHog command
        if state.total_repos > 0 or state.total_gists > 0:
            logger.info("")
            logger.highlight("Next step: Run TruffleHog on the results:")
            if args.trufflehog_list:
                logger.info(
                    f"  trufflehog filesystem --file={args.output}.trufflehog.txt"
                )
            else:
                logger.info(
                    "  Use the URLs in the output file with TruffleHog"
                )
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        http_client.close()


if __name__ == "__main__":
    sys.exit(main())

