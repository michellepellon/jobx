#!/usr/bin/env python3
"""Example script demonstrating Parquet output functionality."""

import pandas as pd
from jobx import scrape_jobs

# Scrape jobs
print("Scraping jobs...")
jobs = scrape_jobs(
    search_term="data engineer",
    location="San Francisco, CA",
    results_wanted=20
)

# Display basic info
print(f"\nFound {len(jobs)} jobs")
print("\nFirst 5 jobs:")
print(jobs[["title", "company", "location"]].head())

# Save to Parquet with compression
print("\nSaving to Parquet format...")
jobs.to_parquet("jobs_data.parquet", compression="snappy", index=False)

# Read back and verify
print("\nReading back from Parquet...")
df_loaded = pd.read_parquet("jobs_data.parquet")
print(f"Loaded {len(df_loaded)} jobs from Parquet file")

# Show file size comparison
import os
jobs.to_csv("jobs_data.csv", index=False)
parquet_size = os.path.getsize("jobs_data.parquet")
csv_size = os.path.getsize("jobs_data.csv")

print(f"\nFile size comparison:")
print(f"Parquet: {parquet_size:,} bytes")
print(f"CSV: {csv_size:,} bytes")
print(f"Compression ratio: {csv_size/parquet_size:.2f}x")

# Clean up
os.remove("jobs_data.parquet")
os.remove("jobs_data.csv")