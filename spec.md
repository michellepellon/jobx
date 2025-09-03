# JobX Multi-Location Market Analysis Tool Specification

## Executive Summary

A batch processing tool built on top of the existing `jobx` job scraper to analyze compensation data for a specific job role (e.g., Board Certified Behavioral Analyst - BCBA) across multiple geographic locations. The tool will search 160+ locations organized by markets and regions, aggregate the data, and produce comprehensive statistical analyses of compensation trends at the market level.

## Core Requirements

### 1. Geographic Coverage
- **Locations**: ~160 predefined locations
- **Search Radius**: 25 miles from each location's zip code
- **Organization**: Locations grouped by Market and Region
- **Configuration**: YAML format for location data

### 2. Search Parameters
- **Job Title**: Single job type per run (e.g., "Board Certified Behavioral Analyst" or "BCBA")
- **Results per Location**: 200+ job postings
- **Job Sites**: Both LinkedIn and Indeed
- **Position Types**: All (remote, hybrid, on-site)
- **Time Filters**: None (all available postings)
- **Compensation**: Only analyze jobs with explicit salary data

### 3. Execution Model
- **Frequency**: Quarterly manual execution
- **Concurrency**: Batch processing, 5 locations simultaneously
- **Error Handling**: Continue on failure with logging
- **No Retry Logic**: Failed locations logged but not retried

### 4. Statistical Analysis

#### 4.1 Descriptive Statistics
- Mean (μ)
- Median (robust to skew)
- Mode
- Range (max - min)
- Standard Deviation (σ)
- Coefficient of Variation (σ/μ)

#### 4.2 Percentiles & Quantiles
- 10th percentile (p10)
- 25th percentile (p25)
- 50th percentile (p50/median)
- 75th percentile (p75)
- 90th percentile (p90)
- Interquartile Range (IQR = p75 - p25)

#### 4.3 Distribution Shape Metrics
- Skewness (indicates long tail)
- Kurtosis (highlights fat-tailed distributions)

#### 4.4 Data Quality Requirements
- **Minimum Sample Size**: 100 job postings with salary data per market
- **Insufficient Data Handling**: Flag markets with <100 salary data points

### 5. Output Structure

#### 5.1 Directory Structure
```
YYYY-MM-DD_BCBA_Analysis/
├── {market_name}_stats.csv      # Statistical analysis per market
├── summary_all_markets.csv      # Consolidated overview
└── execution_log.txt            # Detailed execution log
```

#### 5.2 Market Statistics CSV Columns
- Market name
- Region
- Location count in market
- Data collection date
- Total postings analyzed
- Postings with salary data
- Data sufficiency flag (sufficient/insufficient)
- All statistical measures listed in Section 4

#### 5.3 Summary Report
- Consolidated view of all markets
- Comparison metrics across markets
- Data quality indicators

### 6. Configuration File Format

#### 6.1 YAML Structure
```yaml
job_title: "Board Certified Behavioral Analyst"
search_radius: 25
results_per_location: 200

markets:
  - name: "Northeast"
    regions:
      - name: "New England"
        locations:
          - name: "Boston Office"
            address: "123 Main St, Boston, MA"
            zip_code: "02101"
          - name: "Providence Office"
            address: "456 Water St, Providence, RI"
            zip_code: "02903"
      - name: "Mid-Atlantic"
        locations:
          - name: "NYC Office"
            address: "789 Broadway, New York, NY"
            zip_code: "10001"
```

### 7. Logging Requirements

#### 7.1 Log Content
- Timestamp for each operation
- Location name and zip code
- Success/failure status
- Number of jobs found
- Number with salary data
- Error messages if applicable
- Batch completion markers

#### 7.2 Log Format
```
2024-01-15 09:00:01 | INFO  | Starting batch 1/32 (5 locations)
2024-01-15 09:00:02 | INFO  | Boston Office (02101) - Starting search
2024-01-15 09:02:15 | SUCCESS | Boston Office (02101) - 215 jobs found, 98 with salary
2024-01-15 09:02:16 | ERROR | Providence Office (02903) - Connection timeout
2024-01-15 09:05:30 | INFO  | Batch 1/32 completed - 4/5 successful
```

## Technical Implementation Notes

### Dependencies
- Base: `jobx` package (existing job scraper)
- Statistical: `pandas`, `numpy`, `scipy`
- Configuration: `pyyaml`
- Logging: Python `logging` module
- Concurrency: `concurrent.futures.ThreadPoolExecutor`

### Key Functions Needed
1. **Configuration Loader**: Parse YAML and validate structure
2. **Batch Executor**: Manage concurrent execution with 5-location batches
3. **Data Aggregator**: Combine location results by market
4. **Statistics Calculator**: Compute all required metrics
5. **Report Generator**: Create CSV outputs with proper formatting
6. **Logger Manager**: Handle comprehensive logging

### Error Handling Strategy
- Network failures: Log and continue
- Insufficient data: Flag in output and continue
- Invalid location: Log and skip
- Rate limiting: Implement delays between batches

## Business Applications

### Market Intelligence
- **Benchmarking**: Compare median vs. 90th percentile salaries across metros
- **Equity Analysis**: Identify compression (narrow distributions) vs. spread (wide distributions)
- **Forecasting**: Use fitted distributions to simulate wage trends under different demand scenarios
- **Competitive Positioning**: Understand market rates for talent acquisition and retention

### Reporting Cadence
- Quarterly execution aligns with:
  - Compensation review cycles
  - Budget planning periods
  - Market trend analysis
  - Strategic workforce planning

## Success Criteria

1. **Data Coverage**: Successfully process 80%+ of locations per run
2. **Statistical Validity**: Achieve 100+ salary data points for 70%+ of markets
3. **Execution Time**: Complete full 160-location scan within 2-3 hours
4. **Output Quality**: Generate clean, analysis-ready CSV files with no manual cleanup required
5. **Reliability**: Tool runs without manual intervention once started

## Future Enhancements (Out of Current Scope)

- Historical trend tracking across quarters
- Automated scheduling via cron/Task Scheduler
- Email notifications upon completion
- Interactive dashboard for results visualization
- Multiple job titles in single run
- Geographic clustering analysis
- Cost of living adjustments
- Competition density analysis

## Acceptance Criteria

The tool will be considered complete when it can:
1. Read a YAML configuration file with 160+ locations
2. Execute searches in batches of 5 concurrently
3. Generate market-level statistical analyses
4. Produce all specified CSV outputs
5. Handle errors gracefully with comprehensive logging
6. Complete a full run in under 3 hours
7. Require no manual intervention during execution