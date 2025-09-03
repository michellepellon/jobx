# JobX Market Analysis Tool

A batch processing tool for analyzing job market compensation data across multiple geographic locations.

## Features

- **Multi-location Search**: Search up to 160+ locations organized by markets and regions
- **Concurrent Processing**: Execute searches in batches of 5 locations simultaneously
- **Comprehensive Statistics**: Calculate mean, median, percentiles, skewness, kurtosis, and more
- **Market-level Aggregation**: Group and analyze data at the market level
- **Data Quality Flags**: Identify markets with insufficient data (<100 samples)
- **Detailed Logging**: Track execution progress with timestamps and success/failure status
- **CSV Reports**: Generate individual market reports and summary across all markets

## Installation

The market analysis tool is included with jobx. Ensure you have the latest version installed:

```bash
uv pip install -e .
```

## Usage

### Basic Usage

```bash
jobx-market config.yaml
```

### With Options

```bash
# Verbose output
jobx-market config.yaml -v

# Custom output directory
jobx-market config.yaml -o results/Q1_2024

# Lower sample size threshold
jobx-market config.yaml --min-sample 50

# Dry run to validate configuration
jobx-market config.yaml --dry-run
```

## Configuration File Format

Create a YAML configuration file with your locations:

```yaml
job_title: "Board Certified Behavioral Analyst"
search_radius: 25  # miles
results_per_location: 200
batch_size: 5  # concurrent searches

markets:
  - name: "Northeast"
    regions:
      - name: "New England"
        locations:
          - name: "Boston Metro"
            address: "Boston, MA"
            zip_code: "02108"
          - name: "Cambridge"
            address: "Cambridge, MA"
            zip_code: "02139"
```

See `example_market_config.yaml` for a complete example with 50 locations.

## Output Structure

The tool creates a dated directory with the following files:

```
2024-01-15_BCBA_Analysis/
├── Northeast_stats.csv          # Market statistics
├── Southeast_stats.csv          # Market statistics
├── summary_all_markets.csv      # Consolidated summary
└── execution_log.txt            # Detailed execution log
```

## Market Statistics

Each market report includes:

### Descriptive Statistics
- Mean, Median, Mode
- Range (max - min)
- Standard Deviation
- Coefficient of Variation

### Percentiles
- P10, P25, P50, P75, P90
- Interquartile Range (IQR)

### Distribution Shape
- Skewness (indicates salary distribution tail)
- Kurtosis (identifies extreme salary outliers)

### Data Quality
- Sample size
- Data sufficiency flag (100+ samples required)

## Performance

- Typical execution time: 2-3 hours for 160 locations
- Searches are rate-limited with 5-second delays between batches
- Failed locations are logged but don't stop execution

## Example Workflow

1. **Create Configuration File**
   ```bash
   cp example_market_config.yaml my_analysis.yaml
   # Edit my_analysis.yaml with your locations
   ```

2. **Validate Configuration**
   ```bash
   jobx-market my_analysis.yaml --dry-run
   ```

3. **Run Analysis**
   ```bash
   jobx-market my_analysis.yaml -v
   ```

4. **Review Results**
   - Check `execution_log.txt` for any errors
   - Open `summary_all_markets.csv` for overview
   - Analyze individual market CSV files for details

## Troubleshooting

### Insufficient Data
If a market shows "INSUFFICIENT" data:
- Increase `results_per_location` in config
- Add more locations to that market
- Lower `--min-sample` threshold (not recommended)

### Failed Locations
Check `execution_log.txt` for specific errors:
- Network timeouts: Re-run analysis
- Invalid zip codes: Verify configuration
- Rate limiting: Reduce batch_size

### Memory Issues
For very large analyses:
- Process markets separately
- Reduce `results_per_location`
- Use a machine with more RAM

## Business Applications

- **Compensation Benchmarking**: Compare salaries across metro areas
- **Talent Strategy**: Identify markets with competitive advantages
- **Budget Planning**: Forecast compensation costs by location
- **Market Entry**: Evaluate new market compensation requirements