# jobx

A modern, powerful job scraper for LinkedIn, Indeed and beyond.

## ✨ Features

- 🚀 **Concurrent scraping** from multiple job boards
- 🎯 **Advanced filtering** by location, salary, job type, and more
- 🔍 **Confidence scoring** to rank job relevance based on search terms
- 📊 **Pandas integration** for data analysis and export
- 💾 **Multiple output formats** including CSV and Apache Parquet
- 🔒 **Type-safe** with full mypy compatibility
- 📈 **Structured logging** with JSON output support
- ⚡ **High performance** with async/await patterns
- 🛡️ **Robust error handling** and retry mechanisms

## 🚀 Quick Start

### Installation

```bash
# Using uv (recommended)
uv add jobx

# Using pip
pip install jobx
```

### Basic Usage

```python
from jobx import scrape_jobs

# Search for Python developer jobs
jobs = scrape_jobs(
    search_term="python developer",
    location="New York, NY",
    results_wanted=50
)

print(f"Found {len(jobs)} jobs")
print(jobs[["title", "company", "location", "confidence_score"]].head())

# Save to different formats
jobs.to_csv("jobs.csv", index=False)
jobs.to_parquet("jobs.parquet", index=False)
```

### Command Line Usage

```bash
# Save as CSV (default)
jobx -q "data engineer" -l "San Francisco" -o results.csv

# Save as Parquet for better performance and compression
jobx -q "data engineer" -l "San Francisco" -o results.parquet -f parquet

# Scrape from specific sites and save as Parquet
jobx -s linkedin indeed -q "ML engineer" -l "Remote" -n 100 -o ml_jobs.parquet -f parquet

# Filter by confidence score (0.0-1.0) to get only highly relevant results
jobx -q "python developer" -l "New York" -c 0.7 -o relevant_jobs.csv

# Track SERP position and identify competitor postings vs your company
jobx -q "software engineer" -l "Seattle" --track-serp --my-company "Acme Corp" "Acme Inc" -o serp_tracked.csv

# Use environment variable for company names
export JOBX_MY_COMPANY="Acme Corp,Acme Inc"
jobx -q "data scientist" -l "Remote" --track-serp -o tracked_jobs.parquet -f parquet
```

## 📊 Market Analysis Tool

### Comprehensive Compensation Analysis

jobx includes a powerful market analysis tool for analyzing compensation data across geographic regions with support for:
- **Multi-location job searches** across configured markets and centers
- **Center-level payband comparison** with actual market data
- **Tufte-style visualization** comparing your paybands to market statistics
- **Statistical analysis** with percentiles, IQR, and distribution metrics

```bash
# Run market analysis with visualization
source venv/bin/activate
python -m jobx.market_analysis.cli config.yaml --visualize --min-sample 10 -v -o output_dir

# Options:
#   --visualize         Generate compensation comparison charts
#   --visualize-only    Only generate charts from existing data (skip job searches)
#   --min-sample N      Minimum salary data points required (default: 30)
#   -v, --verbose       Show detailed progress
#   -o, --output        Output directory name
```

### Configuration Structure

The market analysis tool uses a YAML configuration with hierarchical structure:

```yaml
roles:
  - id: rbt
    name: "Registered Behavior Technician (RBT)"
    pay_type: hourly
    search_terms: ["RBT", "behavior technician", "ABA therapist"]
  - id: bcba
    name: "Board Certified Behavior Analyst (BCBA)"
    pay_type: salary
    search_terms: ["BCBA", "behavior analyst", "clinical supervisor"]

regions:
  - name: "Southeast"
    markets:
      - name: "Florida"
        centers:
          - name: "Miami"
            location: "Miami, FL"
            paybands:
              rbt: {min: 18.00, max: 22.00}
              bcba: {min: 70000, max: 85000}
          - name: "Orlando"
            location: "Orlando, FL"
            paybands:
              rbt: {min: 17.00, max: 21.00}
              bcba: {min: 68000, max: 82000}
```

### Visualization Output

The tool generates Tufte-style comparison charts showing:
- **Your payband range** (light green background area)
- **Market IQR** (25th-75th percentile box in gray)
- **Market median** (bold black line)
- **Min/max whiskers** from actual job data
- **Gap analysis** showing if market median is within/above/below your band

## 🎯 Advanced Usage

### Confidence Scoring

jobx includes a confidence scoring system that ranks job relevance based on how well they match your search terms and location:

```python
from jobx import scrape_jobs

jobs = scrape_jobs(
    search_term="python developer",
    location="New York",
    results_wanted=100
)

# Jobs are automatically sorted by confidence score (highest first)
print(jobs[['title', 'company', 'confidence_score']].head(10))

# Filter for highly relevant jobs (70%+ confidence)
relevant_jobs = jobs[jobs['confidence_score'] >= 0.7]
print(f"Found {len(relevant_jobs)} highly relevant jobs out of {len(jobs)} total")

# Analyze confidence distribution
print(f"Average confidence: {jobs['confidence_score'].mean():.2%}")
print(f"Jobs with 80%+ confidence: {len(jobs[jobs['confidence_score'] >= 0.8])}")
```

The confidence score (0.0-1.0) is calculated based on:
- **Title match (50%)**: How well the job title matches your search terms
- **Description match (30%)**: Keyword matching in the job description
- **Location match (20%)**: Proximity to your specified location (remote jobs always score 1.0)

### SERP Position Tracking

Track where job postings appear in search results (page and rank) to understand visibility and compare your company's postings against competitors:

```python
from jobx import scrape_jobs

# Track SERP positions and identify your company's postings
jobs = scrape_jobs(
    search_term="machine learning engineer",
    location="Boston",
    track_serp=True,
    my_company_names=["Acme Corp", "Acme Inc."],
    results_wanted=100
)

# Analyze SERP visibility
print(f"Average position: {jobs['serp_absolute_rank'].mean():.1f}")
print(f"Page 1 listings: {len(jobs[jobs['serp_page_index'] == 0])}")
print(f"Sponsored posts: {jobs['serp_is_sponsored'].sum()}")

# Compare your company vs competitors
my_company_jobs = jobs[jobs['is_my_company'] == True]
competitor_jobs = jobs[jobs['is_my_company'] == False]

print(f"Your company: {len(my_company_jobs)} postings")
print(f"Average rank: {my_company_jobs['serp_absolute_rank'].mean():.1f}")
print(f"Competitors: {len(competitor_jobs)} postings")
```

SERP tracking adds these columns to your results:
- **serp_page_index**: 0-based page number (0 = first page)
- **serp_index_on_page**: Position on the page (0-based)
- **serp_absolute_rank**: Overall rank across all pages (1-based)
- **serp_page_size_observed**: Number of organic results on the page
- **serp_is_sponsored**: Whether the posting is promoted/sponsored
- **company_normalized**: Normalized company name for matching
- **is_my_company**: Whether it matches your configured company names

### Multi-Site Concurrent Scraping

```python
from jobx import scrape_jobs
from jobx.model import Site, JobType

jobs = scrape_jobs(
    site_name=[Site.LINKEDIN, Site.INDEED],
    search_term="software engineer",
    location="San Francisco, CA",
    distance=50,
    job_type=JobType.FULL_TIME,
    is_remote=True,
    easy_apply=True,  # LinkedIn only
    results_wanted=200,
    enforce_annual_salary=True,
    linkedin_fetch_description=True,
    verbose=2
)
```

### Salary Analysis and Filtering

```python
# Filter high-paying remote positions
high_paying_remote = jobs[
    (jobs['is_remote'] == True) &
    (jobs['min_amount'] >= 120000) &
    (jobs['currency'] == 'USD') &
    (jobs['interval'] == 'yearly')
]

# Group by company and analyze
company_stats = high_paying_remote.groupby('company').agg({
    'min_amount': ['count', 'mean'],
    'max_amount': 'mean',
    'title': lambda x: ', '.join(x.unique()[:3])
}).round(0)

print(company_stats)

# Save filtered results as Parquet for efficient storage
high_paying_remote.to_parquet("high_paying_remote_jobs.parquet", 
                              compression='snappy',
                              index=False)
```

## 📊 Data Structure

Each job entry contains comprehensive information:

```python
# Core fields
job_columns = [
    'title', 'company', 'location', 'job_url', 'description',
    'date_posted', 'is_remote', 'job_type', 'site',
    'min_amount', 'max_amount', 'currency', 'interval',
    'salary_source', 'emails', 'easy_apply', 'confidence_score'
]

# Location details
location_fields = ['city', 'state', 'country']

# Compensation analysis
salary_analysis = jobs.groupby('site').agg({
    'min_amount': ['count', 'mean', 'median'],
    'max_amount': ['mean', 'median'],
    'is_remote': 'sum'
})
```

## 🔧 Configuration

### Environment Variables

```bash
# Enable structured JSON logging
export JOBX_LOG_JSON=true

# Set logging level
export JOBX_LOG_LEVEL=DEBUG

# Configure logging context
export JOBX_LOG_CONTEXT=true
```

## 🛠️ Development

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Development Setup

```bash
# Clone the repository
git clone https://github.com/michellepellon/jobx.git
cd jobx

# Install with development dependencies
uv install -e ".[dev]"

# Run tests
uv run pytest

# Run linting
uv run ruff check jobx/
uv run ruff format jobx/

# Run type checking
uv run mypy jobx/

# Run security scanning
uv run bandit -r jobx/
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=jobx --cov-report=html

# Run integration tests only
uv run pytest -m integration

# Run excluding slow tests
uv run pytest -m "not slow"
```

### Code Quality

The project maintains high code quality standards:

- **Formatting**: `ruff format` and `black`
- **Linting**: `ruff` with comprehensive rule set
- **Type checking**: `mypy` in strict mode
- **Security**: `bandit` and `safety`
- **Testing**: `pytest` with 90%+ coverage requirement

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](docs/contributing.md) for details on:

- Code of conduct
- Development workflow
- Testing requirements
- Documentation standards

### Quick Contribution Setup

```bash
# Fork and clone the repo
git clone https://github.com/yourusername/jobx.git
cd jobx

# Create a feature branch
git checkout -b feature/your-feature-name

# Install development dependencies
uv install -e ".[dev]"

# Make your changes and run tests
uv run pytest
uv run ruff check jobx/
uv run mypy jobx/

# Commit and push
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

- 🐛 [Report bugs](https://github.com/michellepellon/jobx/issues)
- 💬 [Request features](https://github.com/michellepellon/jobx/issues)
- 📧 Contact: mgracepellon@gmail.com
