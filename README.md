# jobx

A modern, powerful job scraper for LinkedIn, Indeed and beyond.

## ✨ Features

- 🚀 **Concurrent scraping** from multiple job boards
- 🎯 **Advanced filtering** by location, salary, job type, and more
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
print(jobs[["title", "company", "location", "salary_source"]].head())

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
```

## 🎯 Advanced Usage

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
    'salary_source', 'emails', 'easy_apply'
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
