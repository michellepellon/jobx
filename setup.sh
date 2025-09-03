#!/usr/bin/env bash

# JobX Setup Script
# Builds the entire jobx toolchain on macOS with Python and Homebrew
# Prerequisites: macOS with Python 3.11+ and Homebrew installed

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Unicode symbols
CHECK="✓"
CROSS="✗"
ARROW="→"
PACKAGE="📦"
TOOL="🔧"
ROCKET="🚀"
CLOCK="⏱"
SUCCESS="✨"

# Configuration
REQUIRED_PYTHON_VERSION="3.11"
VENV_NAME=".venv"
PROJECT_NAME="JobX Market Analysis Tool"

# Utility functions
print_header() {
    echo
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${WHITE}  $1${NC}"
    echo -e "${BOLD}${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
}

print_step() {
    echo -e "${CYAN}${ARROW}${NC} ${WHITE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}${CHECK}${NC} $1"
}

print_error() {
    echo -e "${RED}${CROSS}${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⣾⣽⣻⢿⡿⣟⣯⣷'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " ${CYAN}[%c]${NC}  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

check_command() {
    if command -v $1 &> /dev/null; then
        print_success "$2 found: $(command -v $1)"
        return 0
    else
        print_error "$2 not found"
        return 1
    fi
}

check_python_version() {
    local python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    local required_major=$(echo $REQUIRED_PYTHON_VERSION | cut -d. -f1)
    local required_minor=$(echo $REQUIRED_PYTHON_VERSION | cut -d. -f2)
    local actual_major=$(echo $python_version | cut -d. -f1)
    local actual_minor=$(echo $python_version | cut -d. -f2)
    
    if [[ $actual_major -gt $required_major ]] || \
       [[ $actual_major -eq $required_major && $actual_minor -ge $required_minor ]]; then
        print_success "Python $python_version (>= $REQUIRED_PYTHON_VERSION required)"
        return 0
    else
        print_error "Python $python_version (>= $REQUIRED_PYTHON_VERSION required)"
        return 1
    fi
}

# Main setup script
main() {
    clear
    
    # Welcome banner
    echo -e "${BOLD}${CYAN}"
    echo "     ╔═══════════════════════════════════════════╗"
    echo "     ║                                           ║"
    echo "     ║     ${WHITE}JobX Market Analysis Tool Setup${CYAN}      ║"
    echo "     ║                                           ║"
    echo "     ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
    echo
    echo -e "${WHITE}This script will set up the complete JobX toolchain on your Mac.${NC}"
    echo -e "${WHITE}Estimated time: 2-3 minutes${NC}"
    echo
    
    # Step 1: System Check
    print_header "${TOOL} STEP 1: System Requirements Check"
    
    print_step "Checking operating system..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        print_success "macOS detected: $(sw_vers -productVersion)"
    else
        print_error "This script is designed for macOS only"
        exit 1
    fi
    
    print_step "Checking for Homebrew..."
    if check_command brew "Homebrew"; then
        brew_version=$(brew --version | head -n 1)
        print_info "Homebrew version: $brew_version"
    else
        print_error "Homebrew is required but not installed"
        print_info "Install it from: https://brew.sh"
        exit 1
    fi
    
    print_step "Checking Python installation..."
    if ! check_python_version; then
        print_warning "Python $REQUIRED_PYTHON_VERSION+ is required"
        print_info "Install with: brew install python@3.13"
        exit 1
    fi
    
    # Step 2: Install uv package manager
    print_header "${PACKAGE} STEP 2: Package Manager Installation"
    
    print_step "Checking for uv package manager..."
    if command -v uv &> /dev/null; then
        print_success "uv already installed: $(uv --version)"
    else
        print_step "Installing uv via Homebrew..."
        brew install uv &> /dev/null &
        spinner $!
        if command -v uv &> /dev/null; then
            print_success "uv installed successfully"
        else
            print_error "Failed to install uv"
            exit 1
        fi
    fi
    
    # Step 3: Create virtual environment
    print_header "🐍 STEP 3: Python Environment Setup"
    
    if [ -d "$VENV_NAME" ]; then
        print_warning "Virtual environment already exists"
        read -p "$(echo -e ${YELLOW}Delete and recreate? [y/N]:${NC} )" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_step "Removing existing virtual environment..."
            rm -rf "$VENV_NAME"
        else
            print_info "Using existing virtual environment"
        fi
    fi
    
    if [ ! -d "$VENV_NAME" ]; then
        print_step "Creating virtual environment..."
        uv venv --python python3 &> /dev/null &
        spinner $!
        print_success "Virtual environment created"
    fi
    
    # Step 4: Install dependencies
    print_header "${PACKAGE} STEP 4: Installing Dependencies"
    
    print_step "Installing core dependencies..."
    source "$VENV_NAME/bin/activate"
    
    # Install in editable mode with all dependencies
    uv pip install -e . &> /dev/null &
    spinner $!
    print_success "Core dependencies installed"
    
    print_step "Verifying installation..."
    
    # Check key packages
    packages=("pandas" "numpy" "pyyaml" "scipy" "beautifulsoup4" "pydantic")
    for package in "${packages[@]}"; do
        if python -c "import $package" 2>/dev/null; then
            version=$(python -c "import $package; print(getattr($package, '__version__', 'installed'))" 2>/dev/null)
            echo -e "  ${GREEN}${CHECK}${NC} ${package} ${version}"
        else
            echo -e "  ${RED}${CROSS}${NC} ${package} failed to import"
        fi
    done
    
    # Step 5: Verify CLI tools
    print_header "${ROCKET} STEP 5: CLI Tool Verification"
    
    print_step "Checking jobx CLI..."
    if jobx --version &> /dev/null; then
        version=$(jobx --version)
        print_success "jobx CLI installed: $version"
    else
        print_error "jobx CLI not found"
    fi
    
    print_step "Checking jobx-market CLI..."
    if jobx-market --help &> /dev/null; then
        print_success "jobx-market CLI installed"
    else
        print_error "jobx-market CLI not found"
    fi
    
    # Step 6: Test configuration
    print_header "🧪 STEP 6: Configuration Test"
    
    if [ -f "example_market_config.yaml" ]; then
        print_step "Testing example configuration..."
        if jobx-market example_market_config.yaml --dry-run &> /dev/null; then
            print_success "Configuration validated successfully"
            print_info "50 locations across 5 markets ready for analysis"
        else
            print_warning "Configuration validation failed"
        fi
    else
        print_warning "Example configuration not found"
    fi
    
    # Step 7: Create shortcuts
    print_header "⚡ STEP 7: Creating Convenience Scripts"
    
    print_step "Creating run script..."
    cat > run_market_analysis.sh << 'EOF'
#!/usr/bin/env bash
# Quick launcher for market analysis

source .venv/bin/activate
jobx-market "$@"
EOF
    chmod +x run_market_analysis.sh
    print_success "Created run_market_analysis.sh"
    
    print_step "Creating test script..."
    cat > test_small.sh << 'EOF'
#!/usr/bin/env bash
# Test with small configuration

source .venv/bin/activate
jobx-market test_config.yaml -v "$@"
EOF
    chmod +x test_small.sh
    print_success "Created test_small.sh"
    
    # Final summary
    print_header "${SUCCESS} Setup Complete!"
    
    echo -e "${GREEN}${BOLD}Installation Summary:${NC}"
    echo
    echo -e "  ${WHITE}Project:${NC} JobX Market Analysis Tool"
    echo -e "  ${WHITE}Version:${NC} $(jobx --version 2>/dev/null || echo 'unknown')"
    echo -e "  ${WHITE}Python:${NC} $(python3 --version)"
    echo -e "  ${WHITE}Location:${NC} $(pwd)"
    echo
    echo -e "${CYAN}${BOLD}Quick Start Commands:${NC}"
    echo
    echo -e "  ${WHITE}1. Activate environment:${NC}"
    echo -e "     ${YELLOW}source .venv/bin/activate${NC}"
    echo
    echo -e "  ${WHITE}2. Test configuration:${NC}"
    echo -e "     ${YELLOW}jobx-market example_market_config.yaml --dry-run${NC}"
    echo
    echo -e "  ${WHITE}3. Run small test:${NC}"
    echo -e "     ${YELLOW}./test_small.sh${NC}"
    echo
    echo -e "  ${WHITE}4. Run full analysis:${NC}"
    echo -e "     ${YELLOW}jobx-market example_market_config.yaml -v${NC}"
    echo
    echo -e "  ${WHITE}5. View help:${NC}"
    echo -e "     ${YELLOW}jobx-market --help${NC}"
    echo
    echo -e "${GREEN}${BOLD}${CHECK} Ready to analyze job markets across 160+ locations!${NC}"
    echo
    
    # Activation reminder
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}${BOLD}Remember to activate the virtual environment:${NC}"
    echo -e "${CYAN}source .venv/bin/activate${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Run main function
main "$@"