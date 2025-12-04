"""
Output manager for handling multiple output formats.
Supports live-saving to prevent data loss on crashes.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils import logger
from ..utils.helpers import SearchResult


class OutputManager:
    """
    Manages output in multiple formats with live-saving capability.
    
    Supports: TXT, JSON, CSV, HTML, and ALL formats.
    Implements append-mode saving to prevent data loss on crashes.
    
    Attributes:
        output_path: Base path for output file.
        format: Output format(s).
        results: Accumulated results.
    """
    
    FORMATS = {"txt", "json", "csv", "html", "all"}
    
    def __init__(
        self,
        output_path: str,
        output_format: str = "json",
        domain: str = "",
    ):
        """
        Initialize the output manager.
        
        Args:
            output_path: Base path for output file.
            output_format: Output format (txt/json/csv/html/all).
            domain: Target domain for naming.
        """
        self.base_path = Path(output_path)
        self.format = output_format.lower()
        self.domain = domain
        self.results: List[SearchResult] = []
        self._files_created: Dict[str, Path] = {}
        self._json_buffer: List[Dict] = []
        
        if self.format not in self.FORMATS:
            logger.warning(f"Unknown format '{self.format}', using 'json'")
            self.format = "json"
        
        # Initialize output files
        self._initialize_files()
    
    def _get_file_path(self, ext: str) -> Path:
        """
        Get the output file path for a given extension.
        
        Args:
            ext: File extension.
            
        Returns:
            Path object for the output file.
        """
        base = self.base_path
        if base.suffix:
            # Remove existing extension
            base = base.with_suffix("")
        return base.with_suffix(f".{ext}")
    
    def _initialize_files(self) -> None:
        """Initialize output files based on format."""
        formats_to_init = []
        
        if self.format == "all":
            formats_to_init = ["txt", "json", "csv", "html"]
        else:
            formats_to_init = [self.format]
        
        for fmt in formats_to_init:
            path = self._get_file_path(fmt)
            self._files_created[fmt] = path
            
            # Initialize files with headers
            if fmt == "csv":
                self._init_csv(path)
            elif fmt == "html":
                self._init_html(path)
            elif fmt == "json":
                self._init_json(path)
            elif fmt == "txt":
                self._init_txt(path)
    
    def _init_txt(self, path: Path) -> None:
        """Initialize TXT file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# TrufflePiggie Results\n")
            f.write(f"# Domain: {self.domain}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("#" + "=" * 60 + "\n\n")
    
    def _init_json(self, path: Path) -> None:
        """Initialize JSON file."""
        # JSON will be written at finalization
        pass
    
    def _init_csv(self, path: Path) -> None:
        """Initialize CSV file with headers."""
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "type", "name", "url", "html_url", "owner",
                "created_at", "updated_at", "description", "language", "stars"
            ])
    
    def _init_html(self, path: Path) -> None:
        """Initialize HTML file with header."""
        html_header = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrufflePiggie Results - {self.domain}</title>
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --text-dim: #8b949e;
            --accent: #58a6ff;
            --accent-hover: #79b8ff;
            --success: #3fb950;
            --warning: #d29922;
            --repo-bg: #1f2937;
            --gist-bg: #2d1f3d;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            padding: 2rem 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 2rem;
        }}
        
        h1 {{
            font-size: 2.5rem;
            background: linear-gradient(135deg, #58a6ff, #a371f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .meta {{
            color: var(--text-dim);
            margin-top: 0.5rem;
        }}
        
        .stats {{
            display: flex;
            gap: 2rem;
            justify-content: center;
            margin: 1.5rem 0;
        }}
        
        .stat {{
            background: var(--surface);
            padding: 1rem 2rem;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--accent);
        }}
        
        .stat-label {{
            color: var(--text-dim);
            font-size: 0.875rem;
        }}
        
        .results {{
            display: grid;
            gap: 1rem;
        }}
        
        .result {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            transition: border-color 0.2s, transform 0.2s;
        }}
        
        .result:hover {{
            border-color: var(--accent);
            transform: translateY(-2px);
        }}
        
        .result.repo {{
            border-left: 3px solid var(--success);
        }}
        
        .result.gist {{
            border-left: 3px solid var(--warning);
        }}
        
        .result-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }}
        
        .result-type {{
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .result-type.repo {{
            background: rgba(63, 185, 80, 0.2);
            color: var(--success);
        }}
        
        .result-type.gist {{
            background: rgba(210, 153, 34, 0.2);
            color: var(--warning);
        }}
        
        .result-name {{
            font-size: 1.125rem;
            font-weight: 600;
        }}
        
        .result-name a {{
            color: var(--accent);
            text-decoration: none;
        }}
        
        .result-name a:hover {{
            color: var(--accent-hover);
            text-decoration: underline;
        }}
        
        .result-meta {{
            display: flex;
            gap: 1.5rem;
            color: var(--text-dim);
            font-size: 0.875rem;
            flex-wrap: wrap;
        }}
        
        .result-desc {{
            margin-top: 0.75rem;
            color: var(--text-dim);
        }}
        
        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-dim);
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }}
        
        footer a {{
            color: var(--accent);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🐷 TrufflePiggie Results</h1>
            <p class="meta">Target: <strong>{self.domain}</strong> | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <div class="stats" id="stats">
            <div class="stat">
                <div class="stat-value" id="repo-count">0</div>
                <div class="stat-label">Repositories</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="gist-count">0</div>
                <div class="stat-label">Gists</div>
            </div>
        </div>
        
        <div class="results" id="results">
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_header)
    
    def add_result(self, result: SearchResult) -> None:
        """
        Add a result and save immediately (live-save).
        
        Args:
            result: Search result to add.
        """
        self.results.append(result)
        self._json_buffer.append(result.to_dict())
        
        # Live-save to each format
        if self.format == "all":
            self._append_txt(result)
            self._append_csv(result)
            self._append_html(result)
        elif self.format == "txt":
            self._append_txt(result)
        elif self.format == "csv":
            self._append_csv(result)
        elif self.format == "html":
            self._append_html(result)
    
    def _append_txt(self, result: SearchResult) -> None:
        """Append result to TXT file."""
        path = self._files_created.get("txt")
        if not path:
            return
            
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{result.type.upper()}] {result.name}\n")
            f.write(f"  URL: {result.html_url}\n")
            f.write(f"  Owner: {result.owner}\n")
            if result.description:
                f.write(f"  Description: {result.description[:100]}\n")
            f.write("\n")
    
    def _append_csv(self, result: SearchResult) -> None:
        """Append result to CSV file."""
        path = self._files_created.get("csv")
        if not path:
            return
            
        with open(path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                result.type,
                result.name,
                result.url,
                result.html_url,
                result.owner,
                result.created_at or "",
                result.updated_at or "",
                (result.description or "")[:200],
                result.language or "",
                result.stars,
            ])
    
    def _append_html(self, result: SearchResult) -> None:
        """Append result to HTML file."""
        path = self._files_created.get("html")
        if not path:
            return
        
        type_class = "repo" if result.type == "repository" else "gist"
        desc = result.description[:150] + "..." if result.description and len(result.description) > 150 else (result.description or "")
        
        html_item = f"""
            <div class="result {type_class}">
                <div class="result-header">
                    <span class="result-type {type_class}">{result.type}</span>
                    <span class="result-name">
                        <a href="{result.html_url}" target="_blank">{result.name}</a>
                    </span>
                </div>
                <div class="result-meta">
                    <span>👤 {result.owner}</span>
                    {f'<span>⭐ {result.stars}</span>' if result.stars else ''}
                    {f'<span>💻 {result.language}</span>' if result.language else ''}
                    {f'<span>📅 {result.created_at[:10] if result.created_at else ""}</span>' if result.created_at else ''}
                </div>
                {f'<p class="result-desc">{desc}</p>' if desc else ''}
            </div>
"""
        with open(path, "a", encoding="utf-8") as f:
            f.write(html_item)
    
    def finalize(self, total_repos: int = 0, total_gists: int = 0) -> List[Path]:
        """
        Finalize all output files.
        
        Args:
            total_repos: Total repository count.
            total_gists: Total gist count.
            
        Returns:
            List of created file paths.
        """
        # Finalize JSON
        if "json" in self._files_created:
            self._finalize_json()
        
        # Finalize HTML
        if "html" in self._files_created:
            self._finalize_html(total_repos, total_gists)
        
        return list(self._files_created.values())
    
    def _finalize_json(self) -> None:
        """Write final JSON file."""
        path = self._files_created.get("json")
        if not path:
            return
            
        output = {
            "meta": {
                "tool": "TrufflePiggie",
                "domain": self.domain,
                "generated": datetime.now().isoformat(),
                "total_results": len(self._json_buffer),
            },
            "results": self._json_buffer,
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    
    def _finalize_html(self, total_repos: int, total_gists: int) -> None:
        """Close HTML file with footer."""
        path = self._files_created.get("html")
        if not path:
            return
            
        html_footer = f"""
        </div>
        
        <footer>
            <p>Generated by <strong>TrufflePiggie</strong> | 
            <a href="https://github.com/trufflesecurity/trufflehog" target="_blank">TruffleHog</a></p>
        </footer>
    </div>
    
    <script>
        document.getElementById('repo-count').textContent = '{total_repos}';
        document.getElementById('gist-count').textContent = '{total_gists}';
    </script>
</body>
</html>
"""
        with open(path, "a", encoding="utf-8") as f:
            f.write(html_footer)
    
    def get_trufflehog_targets(self) -> List[str]:
        """
        Get list of URLs for TruffleHog scanning.
        
        Returns:
            List of repository/gist URLs.
        """
        return [r.to_trufflehog_target() for r in self.results]
    
    def export_trufflehog_list(self, output_path: Optional[str] = None) -> Path:
        """
        Export a simple list of URLs for TruffleHog.
        
        Args:
            output_path: Output file path.
            
        Returns:
            Path to the created file.
        """
        if output_path is None:
            output_path = self._get_file_path("trufflehog.txt")
        else:
            output_path = Path(output_path)
        
        with open(output_path, "w", encoding="utf-8") as f:
            for url in self.get_trufflehog_targets():
                f.write(f"{url}\n")
        
        logger.success(f"TruffleHog target list saved to: {output_path}")
        return output_path

