#!/bin/bash

# Slow Market Scraper - Processes prod_config.yaml market by market over 48+ hours
# with extensive anti-detection measures

set -e  # Exit on error

# Configuration
CONFIG_FILE="prod_config.yaml"
OUTPUT_BASE_DIR="Production_Markets_$(date +%Y%m%d)"
LOG_FILE="${OUTPUT_BASE_DIR}_scraper.log"
STATE_FILE="${OUTPUT_BASE_DIR}_state.json"
RESULTS_PER_LOCATION=30  # Reduced for stealth
MIN_SAMPLE=10

# Timing configuration (in seconds)
MIN_MARKET_BREAK=3600      # 1 hour minimum between markets
MAX_MARKET_BREAK=7200      # 2 hours maximum between markets
MIN_CENTER_BREAK=600       # 10 minutes minimum between centers
MAX_CENTER_BREAK=1800      # 30 minutes maximum between centers
LONG_BREAK_INTERVAL=4      # Take a long break every 4 markets
LONG_BREAK_MIN=14400       # 4 hours minimum long break
LONG_BREAK_MAX=21600       # 6 hours maximum long break

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log messages
log_message() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$LOG_FILE"
}

# Function to generate random delay
random_delay() {
    local min=$1
    local max=$2
    echo $((min + RANDOM % (max - min + 1)))
}

# Function to format time duration
format_duration() {
    local seconds=$1
    local hours=$((seconds / 3600))
    local minutes=$(( (seconds % 3600) / 60 ))
    local secs=$((seconds % 60))
    printf "%02d:%02d:%02d" $hours $minutes $secs
}

# Function to save state
save_state() {
    local current_market=$1
    local completed_markets=$2
    cat > "$STATE_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "current_market": "$current_market",
    "completed_markets": $completed_markets,
    "output_dir": "$OUTPUT_BASE_DIR"
}
EOF
}

# Function to extract markets from config
extract_markets() {
    python3 -c "
import yaml
import sys

with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)
    
markets = set()
for region in config.get('regions', []):
    for market in region.get('markets', []):
        markets.add(market['name'])

for market in sorted(markets):
    print(market)
"
}

# Function to create market-specific config
create_market_config() {
    local market_name=$1
    local temp_config="temp_${market_name// /_}_config.yaml"
    
    python3 -c "
import yaml
import sys

market_name = '$market_name'
output_file = '$temp_config'

with open('$CONFIG_FILE', 'r') as f:
    config = yaml.safe_load(f)

# Create filtered config with only the specified market
filtered_config = {
    'meta': config.get('meta', {}),
    'roles': config.get('roles', []),
    'search': {
        'radius_miles': 25,  # Reduced radius for stealth
        'results_per_location': $RESULTS_PER_LOCATION,
        'batch_size': 1
    },
    'regions': []
}

# Find and include only the specified market
for region in config.get('regions', []):
    filtered_markets = []
    for market in region.get('markets', []):
        if market['name'] == market_name:
            filtered_markets.append(market)
    
    if filtered_markets:
        filtered_region = {
            'name': region['name'],
            'markets': filtered_markets
        }
        filtered_config['regions'].append(filtered_region)

# Write the filtered config
with open(output_file, 'w') as f:
    yaml.dump(filtered_config, f, default_flow_style=False, sort_keys=False)

print(f'Created config for {market_name} with {len(filtered_markets)} markets')
"
}

# Function to run market analysis
run_market_analysis() {
    local market_name=$1
    local market_output_dir="${OUTPUT_BASE_DIR}/${market_name// /_}"
    local temp_config="temp_${market_name// /_}_config.yaml"
    
    log_message "INFO" "${GREEN}Starting analysis for market: ${market_name}${NC}"
    
    # Create market-specific config
    create_market_config "$market_name"
    
    # Run the analysis with safety features enabled (normal mode)
    source venv/bin/activate
    python -m jobx.market_analysis.cli "$temp_config" \
        --visualize \
        --min-sample $MIN_SAMPLE \
        -v \
        -o "$market_output_dir" 2>&1 | tee -a "$LOG_FILE"
    
    local exit_code=$?
    
    # Clean up temp config
    rm -f "$temp_config"
    
    if [ $exit_code -eq 0 ]; then
        log_message "SUCCESS" "${GREEN}✓ Completed market: ${market_name}${NC}"
        return 0
    else
        log_message "ERROR" "${RED}✗ Failed market: ${market_name}${NC}"
        return 1
    fi
}

# Function to show progress
show_progress() {
    local current=$1
    local total=$2
    local percent=$((current * 100 / total))
    local elapsed=$3
    local estimated_total=$((elapsed * total / current))
    local remaining=$((estimated_total - elapsed))
    
    echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Progress: ${current}/${total} markets (${percent}%)${NC}"
    echo -e "${BLUE}Elapsed: $(format_duration $elapsed)${NC}"
    echo -e "${BLUE}Estimated remaining: $(format_duration $remaining)${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"
}

# Main execution
main() {
    log_message "INFO" "${BLUE}Starting Slow Market Scraper${NC}"
    log_message "INFO" "Configuration: $CONFIG_FILE"
    log_message "INFO" "Output directory: $OUTPUT_BASE_DIR"
    log_message "INFO" "Results per location: $RESULTS_PER_LOCATION"
    
    # Create output directory
    mkdir -p "$OUTPUT_BASE_DIR"
    
    # Extract markets from config
    log_message "INFO" "Extracting markets from configuration..."
    mapfile -t MARKETS < <(extract_markets)
    TOTAL_MARKETS=${#MARKETS[@]}
    
    log_message "INFO" "Found $TOTAL_MARKETS markets to process"
    log_message "INFO" "Estimated completion time: 48-72 hours"
    
    # Process each market
    local completed=0
    local failed=0
    local start_time=$(date +%s)
    
    for i in "${!MARKETS[@]}"; do
        local market="${MARKETS[$i]}"
        local market_num=$((i + 1))
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        show_progress $market_num $TOTAL_MARKETS $elapsed
        
        # Save state before processing
        save_state "$market" $completed
        
        # Run the market analysis
        if run_market_analysis "$market"; then
            completed=$((completed + 1))
        else
            failed=$((failed + 1))
            log_message "WARNING" "Continuing despite failure in $market"
        fi
        
        # Determine break duration
        if [ $market_num -lt $TOTAL_MARKETS ]; then
            if [ $((market_num % LONG_BREAK_INTERVAL)) -eq 0 ]; then
                # Long break every N markets
                local break_duration=$(random_delay $LONG_BREAK_MIN $LONG_BREAK_MAX)
                log_message "INFO" "${YELLOW}Taking long break: $(format_duration $break_duration)${NC}"
                log_message "INFO" "Resume at: $(date -d "+$break_duration seconds" "+%Y-%m-%d %H:%M:%S")"
            else
                # Regular break between markets
                local break_duration=$(random_delay $MIN_MARKET_BREAK $MAX_MARKET_BREAK)
                log_message "INFO" "${YELLOW}Taking break: $(format_duration $break_duration)${NC}"
                log_message "INFO" "Next market: ${MARKETS[$((i + 1))]}"
            fi
            
            # Progress bar for break
            local break_end=$(($(date +%s) + break_duration))
            while [ $(date +%s) -lt $break_end ]; do
                local remaining=$((break_end - $(date +%s)))
                printf "\r${YELLOW}Break remaining: $(format_duration $remaining)${NC}    "
                sleep 10
            done
            printf "\r                                                    \r"
        fi
    done
    
    # Final summary
    local total_time=$(($(date +%s) - start_time))
    
    echo -e "\n${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}SCRAPING COMPLETE${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    log_message "INFO" "Total markets processed: $completed/$TOTAL_MARKETS"
    log_message "INFO" "Failed markets: $failed"
    log_message "INFO" "Total execution time: $(format_duration $total_time)"
    log_message "INFO" "Output directory: $OUTPUT_BASE_DIR"
    
    # Clean up state file
    rm -f "$STATE_FILE"
}

# Resume functionality
if [ "$1" == "--resume" ] && [ -f "$STATE_FILE" ]; then
    log_message "INFO" "${YELLOW}Resuming from previous state...${NC}"
    # Load state and continue (implementation would go here)
    log_message "ERROR" "Resume functionality not yet implemented"
    exit 1
fi

# Check prerequisites
if [ ! -f "$CONFIG_FILE" ]; then
    log_message "ERROR" "${RED}Configuration file not found: $CONFIG_FILE${NC}"
    exit 1
fi

if [ ! -d "venv" ]; then
    log_message "ERROR" "${RED}Virtual environment not found. Please run: python -m venv venv${NC}"
    exit 1
fi

# Trap to handle interruption
trap 'log_message "WARNING" "${YELLOW}Script interrupted. State saved to $STATE_FILE${NC}"; exit 130' INT TERM

# Run main execution
main "$@"