#!/usr/bin/env bash

# JobX Diagnostic Script
# Checks system configuration and installation status

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'
BOLD='\033[1m'

# Symbols
CHECK="✓"
CROSS="✗"
INFO="ℹ"
WARNING="⚠"

print_header() {
    echo
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${WHITE}  $1${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}${CHECK}${NC} $2"
        return 0
    else
        echo -e "${RED}${CROSS}${NC} $2"
        return 1
    fi
}

print_info() {
    echo -e "${BLUE}${INFO}${NC}  $1"
}

print_warning() {
    echo -e "${YELLOW}${WARNING}${NC}  $1"
}

main() {
    clear
    
    echo -e "${BOLD}${CYAN}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║       JobX Installation Diagnostic        ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # System Information
    print_header "System Information"
    
    echo -e "${WHITE}Operating System:${NC} $(uname -s) $(uname -r)"
    echo -e "${WHITE}Architecture:${NC} $(uname -m)"
    echo -e "${WHITE}macOS Version:${NC} $(sw_vers -productVersion 2>/dev/null || echo 'N/A')"
    echo -e "${WHITE}Current Directory:${NC} $(pwd)"
    echo -e "${WHITE}User:${NC} $(whoami)"
    
    # Prerequisites Check
    print_header "Prerequisites"
    
    # Check Homebrew
    if command -v brew &> /dev/null; then
        version=$(brew --version | head -n 1 | cut -d' ' -f2)
        check_status 0 "Homebrew $version"
    else
        check_status 1 "Homebrew not found"
        print_info "Install from: https://brew.sh"
    fi
    
    # Check Python
    if command -v python3 &> /dev/null; then
        version=$(python3 --version 2>&1 | cut -d' ' -f2)
        check_status 0 "Python $version"
        
        # Check Python version requirement
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        if [[ $major -ge 3 && $minor -ge 11 ]]; then
            print_info "Python version meets requirements (3.11+)"
        else
            print_warning "Python 3.11+ recommended"
        fi
    else
        check_status 1 "Python3 not found"
    fi
    
    # Check uv
    if command -v uv &> /dev/null; then
        version=$(uv --version 2>&1 | cut -d' ' -f2)
        check_status 0 "uv $version"
    else
        check_status 1 "uv not found"
        print_info "Install with: brew install uv"
    fi
    
    # Virtual Environment Check
    print_header "Virtual Environment"
    
    if [ -d ".venv" ]; then
        check_status 0 "Virtual environment exists"
        
        # Check if activated
        if [ -n "$VIRTUAL_ENV" ]; then
            check_status 0 "Virtual environment is activated"
            print_info "Path: $VIRTUAL_ENV"
        else
            print_warning "Virtual environment not activated"
            print_info "Activate with: source .venv/bin/activate"
        fi
        
        # Check Python in venv
        if [ -f ".venv/bin/python" ]; then
            venv_python_version=$(.venv/bin/python --version 2>&1 | cut -d' ' -f2)
            print_info "Virtual environment Python: $venv_python_version"
        fi
    else
        check_status 1 "Virtual environment not found"
        print_info "Create with: uv venv"
    fi
    
    # Package Installation Check
    print_header "Package Installation"
    
    if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
        # Check key packages
        packages=("pandas" "numpy" "pyyaml" "scipy" "beautifulsoup4" "pydantic" "requests" "tls_client")
        
        for package in "${packages[@]}"; do
            if .venv/bin/python -c "import ${package//-/_}" 2>/dev/null; then
                version=$(.venv/bin/python -c "import ${package//-/_}; print(getattr(${package//-/_}, '__version__', 'installed'))" 2>/dev/null || echo "unknown")
                check_status 0 "$package ($version)"
            else
                check_status 1 "$package not installed"
            fi
        done
    else
        print_warning "Cannot check packages - virtual environment not found"
    fi
    
    # CLI Tools Check
    print_header "CLI Tools"
    
    if [ -d ".venv" ]; then
        # Check jobx CLI
        if [ -f ".venv/bin/jobx" ]; then
            if .venv/bin/jobx --version &> /dev/null; then
                version=$(.venv/bin/jobx --version)
                check_status 0 "jobx CLI: $version"
            else
                check_status 1 "jobx CLI found but not working"
            fi
        else
            check_status 1 "jobx CLI not installed"
        fi
        
        # Check jobx-market CLI
        if [ -f ".venv/bin/jobx-market" ]; then
            if .venv/bin/jobx-market --help &> /dev/null; then
                check_status 0 "jobx-market CLI installed"
            else
                check_status 1 "jobx-market CLI found but not working"
            fi
        else
            check_status 1 "jobx-market CLI not installed"
        fi
    else
        print_warning "CLI tools require virtual environment"
    fi
    
    # Configuration Files Check
    print_header "Configuration Files"
    
    config_files=(
        "pyproject.toml"
        "example_market_config.yaml"
        "test_config.yaml"
        "spec.md"
        "MARKET_ANALYSIS_README.md"
    )
    
    for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
            size=$(du -h "$file" | cut -f1)
            check_status 0 "$file ($size)"
        else
            check_status 1 "$file not found"
        fi
    done
    
    # Source Code Check
    print_header "Source Code Structure"
    
    directories=(
        "jobx"
        "jobx/market_analysis"
        "tests"
    )
    
    for dir in "${directories[@]}"; do
        if [ -d "$dir" ]; then
            file_count=$(find "$dir" -name "*.py" | wc -l | tr -d ' ')
            check_status 0 "$dir/ ($file_count Python files)"
        else
            check_status 1 "$dir/ not found"
        fi
    done
    
    # Git Status
    print_header "Git Repository"
    
    if [ -d ".git" ]; then
        check_status 0 "Git repository initialized"
        
        if command -v git &> /dev/null; then
            branch=$(git branch --show-current 2>/dev/null || echo "unknown")
            print_info "Current branch: $branch"
            
            # Check for uncommitted changes
            if git diff-index --quiet HEAD -- 2>/dev/null; then
                print_info "No uncommitted changes"
            else
                changed=$(git status --short | wc -l | tr -d ' ')
                print_warning "$changed uncommitted changes"
            fi
        fi
    else
        check_status 1 "Not a git repository"
    fi
    
    # Disk Space
    print_header "Disk Usage"
    
    if [ -d ".venv" ]; then
        venv_size=$(du -sh .venv 2>/dev/null | cut -f1)
        print_info "Virtual environment: $venv_size"
    fi
    
    project_size=$(du -sh . 2>/dev/null | cut -f1)
    print_info "Total project size: $project_size"
    
    # Available disk space
    if command -v df &> /dev/null; then
        available=$(df -h . | tail -1 | awk '{print $4}')
        print_info "Available disk space: $available"
    fi
    
    # Summary and Recommendations
    print_header "Summary"
    
    errors=0
    warnings=0
    
    # Count issues
    if ! command -v brew &> /dev/null; then ((errors++)); fi
    if ! command -v python3 &> /dev/null; then ((errors++)); fi
    if ! command -v uv &> /dev/null; then ((errors++)); fi
    if [ ! -d ".venv" ]; then ((errors++)); fi
    if [ -z "$VIRTUAL_ENV" ]; then ((warnings++)); fi
    
    if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
        echo -e "${GREEN}${BOLD}✨ Everything looks good!${NC}"
        echo
        echo -e "${WHITE}Ready to run market analysis:${NC}"
        echo -e "${CYAN}jobx-market example_market_config.yaml${NC}"
    elif [ $errors -eq 0 ]; then
        echo -e "${YELLOW}${BOLD}⚠ Some warnings detected${NC}"
        echo
        echo -e "${WHITE}Recommended actions:${NC}"
        if [ -z "$VIRTUAL_ENV" ]; then
            echo -e "  • Activate virtual environment: ${CYAN}source .venv/bin/activate${NC}"
        fi
    else
        echo -e "${RED}${BOLD}✗ Issues detected${NC}"
        echo
        echo -e "${WHITE}To fix issues, run:${NC}"
        echo -e "${CYAN}./setup.sh${NC}"
    fi
    
    echo
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}Diagnostic complete • $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

main "$@"