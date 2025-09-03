# JobX Setup Guide

## Quick Start

On a stock macOS laptop with Python 3.11+ and Homebrew installed:

```bash
./setup.sh
```

That's it! The script will handle everything else.

## What Gets Installed

The setup script will:

1. **Verify System Requirements**
   - macOS operating system
   - Homebrew package manager
   - Python 3.11 or higher

2. **Install Package Manager**
   - `uv` - Fast Python package installer

3. **Create Virtual Environment**
   - Isolated Python environment in `.venv/`
   - Python 3.13 (or your system Python)

4. **Install Dependencies**
   - Core: pandas, numpy, requests
   - Analysis: scipy, pyyaml
   - Scraping: beautifulsoup4, tls-client
   - Data: pydantic, pyarrow

5. **Configure CLI Tools**
   - `jobx` - Main job scraping tool
   - `jobx-market` - Market analysis tool

6. **Create Helper Scripts**
   - `run_market_analysis.sh` - Quick launcher
   - `test_small.sh` - Test with small dataset

## Scripts Included

### 🚀 setup.sh
Full installation with color-coded output:
```bash
./setup.sh
```

Features:
- Progress indicators with spinners
- Color-coded success/error messages
- Automatic dependency resolution
- Configuration validation
- Takes 2-3 minutes total

### 🔍 diagnose.sh
Check installation status:
```bash
./diagnose.sh
```

Shows:
- System information
- Package installation status
- Virtual environment details
- Configuration file presence
- Git repository status

### 🗑️ uninstall.sh
Clean removal of installation:
```bash
./uninstall.sh
```

Removes:
- Virtual environment
- Generated scripts
- Python cache files
- Optional: Analysis output directories

Preserves:
- Source code
- Configuration files
- Git repository

## Terminal Output

The setup script provides beautiful, color-coded output:

- 🟢 **Green** - Success messages
- 🔵 **Blue** - Information
- 🟡 **Yellow** - Warnings
- 🔴 **Red** - Errors
- 🟣 **Magenta** - Section headers
- ⚪ **White** - Important text

## Prerequisites

### Required
- **macOS** (Intel or Apple Silicon)
- **Python 3.11+** 
- **Homebrew**

### How to Install Prerequisites

1. **Install Homebrew** (if not installed):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. **Install Python 3.13** (if needed):
```bash
brew install python@3.13
```

## Post-Installation

After successful setup:

1. **Activate the virtual environment**:
```bash
source .venv/bin/activate
```

2. **Test the installation**:
```bash
jobx --version
jobx-market --help
```

3. **Run a test analysis**:
```bash
jobx-market test_config.yaml --dry-run
```

## Troubleshooting

### Permission Denied
If you get "Permission denied" when running scripts:
```bash
chmod +x setup.sh diagnose.sh uninstall.sh
```

### Python Version Issues
If Python 3.11+ is not found:
```bash
brew install python@3.13
brew link python@3.13
```

### Virtual Environment Issues
If the virtual environment is corrupted:
```bash
rm -rf .venv
./setup.sh
```

### Package Installation Failures
If packages fail to install:
```bash
./uninstall.sh
./setup.sh
```

### Diagnostic Information
Run the diagnostic script for detailed status:
```bash
./diagnose.sh
```

## Usage After Setup

### Single Job Search
```bash
jobx -q "python developer" -l "New York" -n 50
```

### Market Analysis
```bash
jobx-market example_market_config.yaml
```

### Quick Test
```bash
./test_small.sh
```

## Color Terminal Requirements

The scripts use ANSI color codes that work in:
- Terminal.app (macOS default)
- iTerm2
- VS Code Terminal
- Most modern terminal emulators

If colors don't display properly, check your terminal's color support:
```bash
echo $TERM
```

Should show: `xterm-256color` or similar.

## Support

If you encounter issues:

1. Run diagnostics: `./diagnose.sh`
2. Check prerequisites are installed
3. Review error messages in color-coded output
4. Try clean reinstall: `./uninstall.sh && ./setup.sh`

## Performance

Typical installation times:
- Prerequisites check: 2-3 seconds
- Virtual environment: 5-10 seconds
- Package installation: 60-90 seconds
- Total time: 2-3 minutes

## Security

The setup script:
- Only installs from PyPI (Python Package Index)
- Creates isolated virtual environment
- Doesn't require sudo/admin privileges
- Doesn't modify system Python
- All changes are local to project directory