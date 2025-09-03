#!/usr/bin/env bash

# JobX Uninstall Script
# Cleanly removes the jobx virtual environment and generated files

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'
BOLD='\033[1m'

# Symbols
CHECK="✓"
CROSS="✗"
ARROW="→"
WARNING="⚠"

print_header() {
    echo
    echo -e "${BOLD}${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${WHITE}  JobX Uninstall${NC}"
    echo -e "${BOLD}${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
}

print_step() {
    echo -e "${CYAN}${ARROW}${NC} ${WHITE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}${CHECK}${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}${WARNING}${NC} $1"
}

main() {
    clear
    print_header
    
    echo -e "${YELLOW}This will remove:${NC}"
    echo -e "  • Virtual environment (.venv)"
    echo -e "  • Generated scripts (run_market_analysis.sh, test_small.sh)"
    echo -e "  • Analysis output directories"
    echo
    echo -e "${WHITE}This will NOT remove:${NC}"
    echo -e "  • Source code"
    echo -e "  • Configuration files"
    echo -e "  • Git repository"
    echo
    
    read -p "$(echo -e ${YELLOW}Continue with uninstall? [y/N]:${NC} )" -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}Uninstall cancelled${NC}"
        exit 0
    fi
    
    echo
    
    # Remove virtual environment
    if [ -d ".venv" ]; then
        print_step "Removing virtual environment..."
        rm -rf .venv
        print_success "Virtual environment removed"
    else
        print_warning "Virtual environment not found"
    fi
    
    # Remove generated scripts
    scripts=("run_market_analysis.sh" "test_small.sh")
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            print_step "Removing $script..."
            rm -f "$script"
            print_success "$script removed"
        fi
    done
    
    # Remove analysis output directories
    print_step "Looking for analysis output directories..."
    analysis_dirs=$(find . -maxdepth 1 -type d -name "*_Analysis" 2>/dev/null | wc -l)
    if [ "$analysis_dirs" -gt 0 ]; then
        echo -e "${YELLOW}Found $analysis_dirs analysis directories${NC}"
        read -p "$(echo -e ${YELLOW}Remove analysis output directories? [y/N]:${NC} )" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf *_Analysis/
            print_success "Analysis directories removed"
        fi
    else
        print_success "No analysis directories found"
    fi
    
    # Remove __pycache__ directories
    print_step "Cleaning Python cache..."
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    print_success "Python cache cleaned"
    
    echo
    echo -e "${GREEN}${BOLD}Uninstall complete!${NC}"
    echo
    echo -e "${CYAN}To reinstall, run:${NC}"
    echo -e "${YELLOW}./setup.sh${NC}"
    echo
}

main "$@"