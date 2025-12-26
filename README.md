# 🐷 TrufflePiggie

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg" alt="Platform">
</p>

**TrufflePiggie** is a powerful GitHub OSINT tool designed to discover repositories and gists related to a target domain. It's built to work seamlessly with [TruffleHog](https://github.com/trufflesecurity/trufflehog) for comprehensive secret scanning.

```
_______ _____  _    _ ______ ______ _      ______ 
 |__   __|  __ \| |  | |  ____|  ____| |    |  ____|
    | |  | |__) | |  | | |__  | |__  | |    | |__   
    | |  |  _  /| |  | |  __|_|  __| | |    |  __|  
    | |  | | \ \| |__| | |  | | |    | |____| |____ 
    |_|  |_|  \_\\____/|_|  |_|_|    |______|______|

  _____ _____  _____  _____ _____ ______ 
 |  __ \_   _|/ ____|/ ____|_   _|  ____|   ^._.^
 | |__) || | | |  __| |  __  | | | |__      ( oo )
 |  ___/ | | | | |_ | | |_ | | | |  __|     /    \
 | |    _| |_| |__| | |__| |_| |_| |____   /      \
 |_|   |_____|\_____|\_____|_____|______| (_/^\/^\_)

                [ @by W4R ]
```

## ⚠️ Disclaimer

**This tool is for educational and authorized security testing purposes only.**

Using this tool against targets without explicit permission is illegal. The authors are not responsible for any misuse or damage caused by this tool. Always obtain proper authorization before performing any security assessments.

## ✨ Features

- 🔍 **Recursive Time Slicing** - Bypasses GitHub's 1000 result limit by intelligently splitting date ranges
- 🔄 **Multi-Token Rotation** - Automatically rotates between multiple GitHub tokens to maximize API usage
- 🛡️ **Rate Limit Handling** - Smart rate limit detection with automatic waiting and token switching
- 🎭 **User-Agent Rotation** - Rotates User-Agents from a configurable list to avoid fingerprinting
- ⏱️ **Configurable Delays** - Set fixed or random delay ranges between requests
- 📊 **Multiple Output Formats** - Export to TXT, JSON, CSV, HTML, or all formats at once
- 💾 **Live Saving** - Results are saved immediately to prevent data loss on crashes
- 🔗 **TruffleHog Integration** - Export URL lists ready for TruffleHog scanning

## 📋 Requirements

- Python 3.10 or higher
- GitHub Personal Access Token(s)

## 🚀 Installation

### Linux/Kali (One Command)

First, create and activate a virtual environment:

```bash
python3 -m venv env
source env/bin/activate
```

Then run the installer:

```bash
cd trufflepiggie && chmod +x install.sh && ./install.sh
```

### Windows

```cmd
cd trufflepiggie && install.bat
```

### Manual (Any OS)

```bash
pip install requests rich pyyaml
```

**That's it!** 3 dependencies, no complex setup.

### 🔄 Updating

Update TrufflePiggie while preserving your tokens:

```bash
python trufflepiggie.py --update
```

This will run `git pull` and automatically backup/restore your `config/tokens/` directory.

## 🔑 GitHub Token Setup

TrufflePiggie requires at least one GitHub Personal Access Token to work.

### Getting a Token

1. Go to [GitHub Settings > Tokens](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Give it a descriptive name (e.g., "TrufflePiggie Scanner")
4. Select these scopes:
   - `repo` - For repository access
   - `gist` - For gist access
5. Click **"Generate token"**
6. Copy the token (starts with `ghp_` or `github_pat_`)

### Adding Tokens

Create a text file in `config/tokens/` with your token(s):

```bash
# Create tokens directory if it doesn't exist
mkdir -p config/tokens

# Add your token(s) - one per line
echo "ghp_your_token_here" > config/tokens/my_tokens.txt
```

**Pro Tip:** Add multiple tokens (one per line) for automatic rotation:

```text
ghp_first_token_xxxxxxxxxxxxx
ghp_second_token_xxxxxxxxxxxxx
github_pat_third_token_xxxxx
```

## 📖 Usage

### Basic Usage

```bash
# Search for a domain (no quotes needed)
python trufflepiggie.py -q example.com -o results

# Search with specific year range
python trufflepiggie.py -q example.com -y 2020-2024 -o example_results

# Export in all formats
python trufflepiggie.py -q example.com -f all -o example_scan

# Search multiple domains from a file
python trufflepiggie.py -l subdomains.txt -o multi_results
```

### All Options

```
usage: trufflepiggie [-h] [-q QUERY] [-l LIST] [-o OUTPUT] [-f {txt,json,csv,html,all}]
                     [-y YEARS] [--repos-only] [--gists-only] [--code-only]
                     [-D DELAY] [-t TOKEN] [-v] [--no-banner] [--trufflehog-list]

🐷 TrufflePiggie - GitHub OSINT Tool for Secret Discovery

options:
  -h, --help            Show this help message and exit
  -q, --query QUERY     Domain or search query (e.g., example.com)
  -l, --list LIST       File with list of domains/subdomains (one per line)
  -o, --output OUTPUT   Output file path (without extension). Default: 'results'
  -f, --format FORMAT   Output format: txt, json, csv, html, all. Default: json
  -y, --years YEARS     Year range (e.g., '2020-2024' or '2023'). Default: 2015-now
  --repos-only          Search only repositories (skip gists)
  --gists-only          Search only gists (skip repositories)
  --code-only           Search only code (skip repository metadata)
  -D, --delay DELAY     Delay between requests: fixed (e.g., '2.5') or range ('1.5-3.5')
  -t, --token TOKEN     Single GitHub token (or use config/tokens/)
  -v, --verbose         Enable verbose output
  --no-banner           Don't display ASCII art banner
  --trufflehog-list     Export a simple URL list for TruffleHog
  --update              Update TrufflePiggie from git (preserves tokens)
```

> **Note:** Use `-q` for a single domain or `-l` for multiple domains from a file. Rate limits are automatically managed between domains.

### Examples

```bash
# Search with custom delay range
python trufflepiggie.py -q example.com -D 1.2-3.8 -o example_results

# Search only repositories, verbose mode
python trufflepiggie.py -q example.com --repos-only -v -o repos

# Quick search with single token
python trufflepiggie.py -q example.com -t ghp_your_token -o quick_scan

# Full scan with TruffleHog integration
python trufflepiggie.py -q example.com -f all --trufflehog-list -o example_full

# Scan multiple subdomains from file
python trufflepiggie.py -l subdomains.txt -f all --trufflehog-list -o multi_scan
```

### Subdomain List Format

Create a text file with one domain per line:

```text
# subdomains.txt
api.example.com
dev.example.com
staging.example.com
admin.example.com
```

Lines starting with `#` are treated as comments and ignored.

## 🔗 TruffleHog Integration

After running TrufflePiggie, use TruffleHog to scan for secrets:

```bash
# Scan individual repositories from results
trufflehog github --repo=https://github.com/user/repo

# Or use the exported URL list
trufflehog filesystem results.trufflehog.txt

# Scan with verification
trufflehog github --repo=https://github.com/user/repo --results=verified,unknown
```

### Cleaning URLs for TruffleHog

You can use this one-liner to extract clean URLs from TrufflePiggie output:

```bash
awk '/URL:/ {print $2}' results.txt > results_clean.txt
```

Then pass them to TruffleHog:

```bash
# All results
cat results_clean.txt | xargs -I {} trufflehog git {} --no-update | tee final-output

# Verified results only
cat results_clean.txt | xargs -I {} trufflehog git {} --no-update --results=verified | tee final-output
```

### 🚀 All-In-One Pipeline

Este oneliner combina **TrufflePiggie + TruffleHog** en un solo comando de pipeline, ejecutando toda la cadena de escaneo de forma automatizada:

```bash
trufflepiggie.py -q example.com -y 2019-2025 -v -D 3.9-5.8 -f txt -o output-1.txt \
&& awk '/URL:/ {print $2}' output-1.txt > output-1_clean.txt \
&& cat output-1_clean.txt | xargs -I {} trufflehog git {} --results=verified --no-update | tee final_output.txt
```

**¿Qué hace?**
1. **TrufflePiggie** busca repositorios y gists relacionados con el dominio objetivo en GitHub
2. **awk** extrae las URLs limpias del output
3. **TruffleHog** escanea cada repositorio encontrado en busca de secretos verificados

**Requisitos:**
- ⚠️ [TruffleHog](https://github.com/trufflesecurity/trufflehog) debe estar instalado
- ⚠️ Ambas herramientas (`trufflepiggie.py` y `trufflehog`) deben estar en el PATH

**Sobre el delay `-D 3.9-5.8`:**

> 🧪 Los rangos de delay `3.9-5.8` segundos han sido **testeados positivamente en entornos reales** de auditorías web y programas de bug bounty, evitando bloqueos por rate limiting de GitHub. Este rango ofrece un buen equilibrio entre velocidad y evasión de detección.

## 📁 Output Formats

### JSON (Default)
```json
{
  "meta": {
    "tool": "TrufflePiggie",
    "domain": "example.com",
    "generated": "2024-12-04T10:30:00",
    "total_results": 42
  },
  "results": [
    {
      "type": "repository",
      "name": "user/repo",
      "url": "https://api.github.com/repos/user/repo",
      "html_url": "https://github.com/user/repo",
      "owner": "user",
      "description": "Example repository"
    }
  ]
}
```

### TXT
Simple text format with URLs and metadata.

### CSV
Spreadsheet-compatible format for analysis.

### HTML
Beautiful, interactive HTML report with dark theme.

## ⚙️ Configuration

Edit `config/settings.yaml` to customize defaults:

```yaml
network:
  min_delay: 2.0          # Minimum delay between requests
  max_delay: 5.5          # Maximum delay between requests
  max_retries: 3          # Retry attempts on failure
  timeout: 15             # Request timeout

search:
  per_page: 100           # Results per page (max 100)
  default_years: "2015-2024"
```

## 📊 Rate Limits

GitHub has a complex rate limiting system. The **Search API** (what TrufflePiggie uses) has **much stricter limits** than the Core API:

### Search API Limits (Critical!)

| Authentication | Limit | Window | Notes |
|----------------|-------|--------|-------|
| **Authenticated (PAT)** | **30 requests** | **1 minute** | Per user, not per token! |
| Unauthenticated | 10 requests | 1 minute | Per IP address |

### Core API Limits (Reference)

| Authentication | Limit | Window |
|----------------|-------|--------|
| Authenticated (PAT) | 5,000 requests | 1 hour |
| GitHub App (Enterprise) | 15,000 requests | 1 hour |
| Unauthenticated | 60 requests | 1 hour |

### ⚠️ Important Notes

1. **Rate limits are per USER, not per token!** If you create 5 tokens from the same GitHub account, they all share the same 30 req/min quota.

2. **Secondary limits (abuse detection)** can trigger if you:
   - Make too many concurrent requests (~100 max)
   - Burst requests too fast (~900 points/min)
   - Hit the same endpoint repeatedly

3. **Pagination limit:** GitHub returns max 1,000 results per search query. TrufflePiggie uses "Recursive Time Slicing" to work around this.

### How TrufflePiggie Handles Rate Limits

1. **Proactive monitoring**: Checks `x-ratelimit-remaining` header BEFORE hitting limits
2. **Token rotation**: Switches to next token when remaining < 2
3. **Retry-After respect**: Honors the `Retry-After` header exactly as GitHub requires
4. **Exponential backoff**: When no Retry-After provided, uses 60s base with exponential increase
5. **Jitter delays**: Random delays between requests (configurable with `-D`)

**Tip:** Use tokens from **different GitHub accounts** (not multiple tokens from same account) for true parallel capacity.

## 🛠️ Troubleshooting

### "No GitHub tokens found"
Add tokens to `config/tokens/my_tokens.txt` (one per line).

### "Rate limit exceeded"
- Add more tokens for rotation
- Increase delay with `-D 3.0-6.0`
- Wait for rate limit reset (shown in console)

### "Abuse detection triggered"
GitHub detected too many requests. The tool will:
1. Sleep for 60 seconds
2. Switch to a different token
3. Resume automatically

### Results seem incomplete
- GitHub limits to 1000 results per query
- TrufflePiggie uses time slicing to work around this
- Very dense days may still be limited

## 📝 License

This project is licensed under the MIT License.

## 🙏 Credits

- Inspired by manual OSINT techniques for GitHub reconnaissance
- Works with [TruffleHog](https://github.com/trufflesecurity/trufflehog) by TruffleSecurity
- Uses [Rich](https://github.com/Textualize/rich) for beautiful CLI output

## 👤 Author

**@W4R**

---

<p align="center">
  <b>Happy Hunting! 🐷🔍</b>
</p>

