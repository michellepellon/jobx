# JobX Market Analysis Tool - Usage Instructions

## Quick Start Guide

This guide covers how to use the jobx-market tool for analyzing BCBA compensation data across multiple locations.

## Prerequisites

Before running the market analysis, ensure you have:

1. ✅ **Virtual environment activated**
2. ✅ **Dependencies installed** (already done via setup.sh)
3. ✅ **Configuration file ready** (bcba_locations_config.yaml)

## Step-by-Step Instructions

### 1. Activate the Virtual Environment

**IMPORTANT**: Always activate the virtual environment before using the tool:

```bash
source .venv/bin/activate
```

You'll know it's activated when you see `(.venv)` in your terminal prompt.

### 2. Verify Installation

Check that the tool is properly installed:

```bash
# Check if jobx-market is available
which jobx-market

# View help information
jobx-market --help
```

### 3. Validate Your Configuration

Before running a full analysis, always validate your configuration:

```bash
jobx-market bcba_locations_config.yaml --dry-run
```

Expected output:
```
Configuration loaded:
  Job Title: Board Certified Behavioral Analyst BCBA
  Markets: 18
  Total Locations: 152
  Search Radius: 25 miles
  Results per Location: 200
  Batch Size: 5

Dry run complete. Configuration is valid.
```

### 4. Run a Test Analysis (Recommended)

Start with a small test to ensure everything works:

```bash
# Test with 2 locations (takes ~5 minutes)
jobx-market test_config.yaml -v
```

This will:
- Search 2 locations (Boston and New York)
- Generate sample output files
- Help verify your setup is working

### 5. Run the Full BCBA Analysis

Once the test succeeds, run the complete analysis:

```bash
# Full analysis with all 152 locations
jobx-market bcba_locations_config.yaml -v
```

**Options you can add:**

```bash
# Custom output directory
jobx-market bcba_locations_config.yaml -v -o results/2024_Q4_BCBA

# Lower minimum sample size (default is 100)
jobx-market bcba_locations_config.yaml -v --min-sample 50

# Quiet mode (no verbose output)
jobx-market bcba_locations_config.yaml
```

## What to Expect

### Execution Time

- **Test run** (2 locations): ~5 minutes
- **Full run** (152 locations): 2-3 hours
- Processes in batches of 5 locations concurrently
- 5-second delay between batches to avoid rate limiting

### Progress Indicators

With verbose mode (`-v`), you'll see:
```
Starting batch 1/31 (5 locations)
SUCCESS | Boston Metro (02108) - 215 jobs found, 98 with salary
SUCCESS | Cambridge (02139) - 187 jobs found, 72 with salary
ERROR | Providence (02903) - Connection timeout
Batch 1/31 completed - 4/5 successful
```

### Output Files

The tool creates a dated directory with your results:

```
2024-12-15_Board_Certified_Behavioral_Analyst_BCBA_Analysis/
├── Central_North_Texas_stats.csv    # Individual market statistics
├── Central_Metro_Dallas_stats.csv
├── East_West_Georgia_stats.csv
├── ... (one file per market)
├── summary_all_markets.csv          # Consolidated overview
└── execution_log.txt                # Detailed execution log
```

## Understanding the Output

### Market Statistics CSV

Each market file contains:
- **Descriptive Statistics**: Mean, median, mode, min, max, range
- **Percentiles**: P10, P25, P50, P75, P90
- **Distribution Metrics**: Skewness, kurtosis
- **Data Quality**: Sample size, sufficiency flag

### Summary Report

The consolidated summary includes:
- Market comparison table
- Overall statistics across all markets
- Data sufficiency indicators
- Markets ranked by median compensation

### Execution Log

Detailed log with:
- Timestamp for each operation
- Success/failure for each location
- Number of jobs found
- Error messages if any

## Troubleshooting

### Common Issues and Solutions

#### 1. "jobx-market: command not found"
```bash
# Solution: Activate virtual environment
source .venv/bin/activate
```

#### 2. "Configuration file not found"
```bash
# Solution: Check you're in the right directory
pwd  # Should show: /Users/mpellon/Documents/jobx
ls *.yaml  # Should list your config files
```

#### 3. "No jobs found" for many locations
- Normal for smaller cities
- Check your internet connection
- May indicate rate limiting (wait and retry)

#### 4. "Connection timeout" errors
- Network issues or rate limiting
- The tool continues despite failures
- Failed locations are logged for manual retry

#### 5. Insufficient data warnings
- Markets with <100 jobs with salary data
- Consider lowering --min-sample threshold
- Or accept that some markets have limited data

## Best Practices

### For Quarterly Runs

1. **Schedule appropriately**: Run during off-peak hours (evening/weekend)
2. **Check disk space**: Need ~100MB for output files
3. **Review logs**: Check execution_log.txt for any issues
4. **Archive results**: Save each quarter's results for trend analysis

### Data Quality

- **Minimum 100 samples**: Default threshold for reliable statistics
- **Check sufficiency flags**: Markets marked "INSUFFICIENT" have limited data
- **Review outliers**: Check if salary ranges seem reasonable

### Performance Tips

- **Stable internet**: Ensure reliable connection for 2-3 hour run
- **Don't interrupt**: Let the process complete even if some locations fail
- **Monitor progress**: Use `-v` flag to see real-time updates

## Interpreting Results

### Compensation Metrics

- **Median vs Mean**: Median is more robust to outliers
- **IQR (P75-P25)**: Shows middle 50% salary range
- **P90**: Top 10% of salaries (senior/specialized roles)
- **Skewness**: 
  - Positive = long tail of high salaries
  - Negative = long tail of low salaries

### Market Comparisons

Use the summary report to:
- Identify highest/lowest paying markets
- Find markets with compressed vs wide salary ranges
- Spot markets with insufficient data for analysis

## Command Reference

```bash
# Basic usage
jobx-market config.yaml

# With options
jobx-market config.yaml \
  -v \                          # Verbose output
  -o results/Q4_2024 \         # Custom output directory
  --min-sample 75              # Lower sample threshold

# Help
jobx-market --help

# Dry run (validate only)
jobx-market config.yaml --dry-run
```

## Next Steps

After successful analysis:

1. **Review summary_all_markets.csv** for overview
2. **Examine individual market files** for detailed statistics
3. **Check execution_log.txt** for any issues
4. **Archive results** for historical comparison
5. **Share findings** with stakeholders

## Support

If you encounter issues:

1. Run diagnostics: `./diagnose.sh`
2. Check execution log for specific errors
3. Verify configuration with `--dry-run`
4. Try test configuration first
5. Ensure virtual environment is activated

## Automation Tips

### Create an Alias

Add to your `~/.zshrc` or `~/.bash_profile`:
```bash
alias jobx-market='source /Users/mpellon/Documents/jobx/.venv/bin/activate && jobx-market'
```

### Create a Run Script

```bash
#!/bin/bash
# quarterly_bcba_analysis.sh
cd /Users/mpellon/Documents/jobx
source .venv/bin/activate
jobx-market bcba_locations_config.yaml -v -o "results/$(date +%Y_Q%q)_BCBA"
```

## Important Notes

⚠️ **Rate Limiting**: The tool includes delays to avoid being blocked
⚠️ **Execution Time**: Full analysis takes 2-3 hours - plan accordingly  
⚠️ **Network Required**: Stable internet connection essential
⚠️ **Data Currency**: Results reflect current job postings only

---

**Ready to run?** Start with:
```bash
source .venv/bin/activate
jobx-market test_config.yaml -v
```