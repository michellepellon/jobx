#!/bin/bash

# Script to run analysis for a single market from prod_config.yaml
# Usage: ./run_single_market.sh "Market Name" [options]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="prod_config.yaml"
TEMP_CONFIG=""

# Function to display usage
usage() {
    echo -e "${BLUE}Usage: $0 \"Market Name\" [options]${NC}"
    echo ""
    echo "Extract and run analysis for a single market from prod_config.yaml"
    echo ""
    echo "Arguments:"
    echo "  Market Name    Name of the market to analyze (e.g., \"Florida\", \"Georgia\")"
    echo ""
    echo "Options:"
    echo "  --min-sample N      Minimum sample size (default: 10)"
    echo "  --no-raw-jobs       Don't save raw job data files"
    echo "  --no-visualize      Skip visualization generation"
    echo "  --no-safety         Disable anti-detection safety features"
    echo "  --output DIR        Output directory name (default: Market_Name_Analysis)"
    echo "  --config FILE       Use alternative config file (default: prod_config.yaml)"
    echo "  -v, --verbose       Enable verbose output"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 \"Florida\""
    echo "  $0 \"Georgia\" --min-sample 30 --no-raw-jobs"
    echo "  $0 \"Carolinas\" --output CAR_Analysis_2025 --verbose"
    exit 0
}

# Function to clean up
cleanup() {
    if [ -n "$TEMP_CONFIG" ] && [ -f "$TEMP_CONFIG" ]; then
        rm -f "$TEMP_CONFIG"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Check if no arguments provided
if [ $# -eq 0 ]; then
    usage
fi

# Parse arguments
MARKET_NAME="$1"
shift

# Default options
MIN_SAMPLE=10
NO_RAW_JOBS=false
VISUALIZE="--visualize"
SAFETY=""
OUTPUT_DIR=""
VERBOSE=""

# Parse optional arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --min-sample)
            MIN_SAMPLE="$2"
            shift 2
            ;;
        --no-raw-jobs)
            NO_RAW_JOBS=true
            shift
            ;;
        --no-visualize)
            VISUALIZE=""
            shift
            ;;
        --no-safety)
            SAFETY="--no-safety"
            shift
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Configuration file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Set default output directory if not specified
if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="${MARKET_NAME// /_}_Analysis_$(date +%Y%m%d)"
fi

# Create temporary config file name
TEMP_CONFIG="temp_${MARKET_NAME// /_}_$(date +%s).yaml"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}Single Market Analysis${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "Market: ${GREEN}$MARKET_NAME${NC}"
echo -e "Config: $CONFIG_FILE"
echo -e "Output: $OUTPUT_DIR"
echo -e "Min Sample: $MIN_SAMPLE"
echo -e "Raw Jobs: $([ "$NO_RAW_JOBS" = true ] && echo "No" || echo "Yes")"
echo -e "Visualize: $([ -n "$VISUALIZE" ] && echo "Yes" || echo "No")"
echo -e "${BLUE}============================================================${NC}"

# Extract market configuration using Python
echo -e "\n${YELLOW}Extracting market configuration...${NC}"

python3 -c "
import yaml
import sys

market_name = '$MARKET_NAME'
output_file = '$TEMP_CONFIG'

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)

    # Create filtered config with only the specified market
    filtered_config = {
        'meta': config.get('meta', {}),
        'roles': config.get('roles', []),
        'search': config.get('search', {}),
        'regions': []
    }

    # Find and include only the specified market
    market_found = False
    for region in config.get('regions', []):
        filtered_markets = []
        for market in region.get('markets', []):
            if market['name'].lower() == market_name.lower():
                filtered_markets.append(market)
                market_found = True
        
        if filtered_markets:
            filtered_region = {
                'name': region['name'],
                'markets': filtered_markets
            }
            filtered_config['regions'].append(filtered_region)

    if not market_found:
        print(f'Error: Market \"{market_name}\" not found in configuration')
        sys.exit(1)

    # Count centers
    total_centers = 0
    for region in filtered_config['regions']:
        for market in region['markets']:
            total_centers += len(market.get('centers', []))

    # Write the filtered config
    with open(output_file, 'w') as f:
        yaml.dump(filtered_config, f, default_flow_style=False, sort_keys=False)

    print(f'✓ Created config for {market_name}')
    print(f'  Centers: {total_centers}')
    print(f'  Roles: {len(filtered_config[\"roles\"])}')
    
except Exception as e:
    print(f'Error: {str(e)}')
    sys.exit(1)
" || exit 1

# Check if temp config was created
if [ ! -f "$TEMP_CONFIG" ]; then
    echo -e "${RED}Error: Failed to create market configuration${NC}"
    exit 1
fi

# Run the analysis
echo -e "\n${YELLOW}Starting market analysis...${NC}"
echo -e "${BLUE}------------------------------------------------------------${NC}"

# Build command
CMD="source venv/bin/activate && python -m jobx.market_analysis.cli \"$TEMP_CONFIG\""
CMD="$CMD --min-sample $MIN_SAMPLE"

if [ -n "$VISUALIZE" ]; then
    CMD="$CMD $VISUALIZE"
fi

if [ -n "$SAFETY" ]; then
    CMD="$CMD $SAFETY"
fi

if [ -n "$VERBOSE" ]; then
    CMD="$CMD $VERBOSE"
fi

CMD="$CMD -o \"$OUTPUT_DIR\""

# Execute the command
eval $CMD

EXIT_CODE=$?

# Clean up raw jobs files if requested
if [ $EXIT_CODE -eq 0 ] && [ "$NO_RAW_JOBS" = true ]; then
    echo -e "\n${YELLOW}Removing raw job data files...${NC}"
    rm -f "$OUTPUT_DIR"/raw_jobs_*.csv
    echo -e "${GREEN}✓ Raw job files removed${NC}"
fi

# Summary
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ Market analysis complete!${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo -e "Market: $MARKET_NAME"
    echo -e "Output: $OUTPUT_DIR"
    
    # Show generated files
    if [ -d "$OUTPUT_DIR" ]; then
        echo -e "\nGenerated files:"
        
        # Count different file types
        CHARTS=$(find "$OUTPUT_DIR" -name "*.png" 2>/dev/null | wc -l)
        CSVS=$(find "$OUTPUT_DIR" -name "*.csv" 2>/dev/null | wc -l)
        
        echo -e "  Charts: $CHARTS"
        echo -e "  CSV Reports: $CSVS"
        
        # Show payband comparison if available
        if [ -f "$OUTPUT_DIR/summary_all_markets.csv" ]; then
            echo -e "\n${YELLOW}Payband Comparison:${NC}"
            python3 -c "
import pandas as pd
try:
    df = pd.read_csv('$OUTPUT_DIR/summary_all_markets.csv')
    if 'market' in df.columns and 'median_salary' in df.columns:
        for _, row in df.iterrows():
            market = row.get('market', 'Unknown')
            median = row.get('median_salary', 0)
            if median > 0:
                print(f'  {market}: \${median:,.0f}')
except:
    pass
"
        fi
    fi
else
    echo -e "\n${RED}✗ Analysis failed with exit code $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi