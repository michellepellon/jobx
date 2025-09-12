#!/usr/bin/env python3
"""
Safe runner for market analysis with built-in breaks and monitoring.
Splits large analysis into manageable chunks with cooling periods.
"""

import sys
import time
import subprocess
import random
from pathlib import Path
from datetime import datetime, timedelta
import yaml
import argparse

class SafeAnalysisRunner:
    def __init__(self, config_path: str, output_base: str = "Safe_Analysis"):
        self.config_path = config_path
        self.output_base = output_base
        self.completed_regions = set()
        self.load_progress()
        
    def load_progress(self):
        """Load previously completed regions from progress file."""
        progress_file = Path(f"{self.output_base}_progress.txt")
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                self.completed_regions = set(line.strip() for line in f)
    
    def save_progress(self, region_name: str):
        """Save completed region to progress file."""
        self.completed_regions.add(region_name)
        with open(f"{self.output_base}_progress.txt", 'a') as f:
            f.write(f"{region_name}\n")
    
    def split_config_by_region(self):
        """Split the main config into separate configs per region."""
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        regions = []
        for region in config.get('regions', []):
            if region['name'] not in self.completed_regions:
                # Create temp config for this region only
                region_config = {
                    'meta': config.get('meta', {}),
                    'roles': config.get('roles', []),
                    'search': config.get('search', {}),
                    'regions': [region]
                }
                regions.append((region['name'], region_config))
        
        return regions
    
    def run_region(self, region_name: str, region_config: dict):
        """Run analysis for a single region."""
        # Save temp config
        temp_config = f"temp_{region_name.replace(' ', '_')}_config.yaml"
        with open(temp_config, 'w') as f:
            yaml.dump(region_config, f, default_flow_style=False, sort_keys=False)
        
        # Run analysis
        output_dir = f"{self.output_base}_{region_name.replace(' ', '_')}"
        cmd = [
            "python", "-m", "jobx.market_analysis.cli",
            temp_config,
            "--visualize",
            "--min-sample", "10",
            "-v",
            "-o", output_dir
        ]
        
        print(f"\n{'='*60}")
        print(f"Starting analysis for region: {region_name}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Output directory: {output_dir}")
        print(f"{'='*60}\n")
        
        try:
            result = subprocess.run(cmd, capture_output=False, text=True)
            if result.returncode == 0:
                print(f"✓ Successfully completed {region_name}")
                self.save_progress(region_name)
            else:
                print(f"✗ Failed to complete {region_name}")
                return False
        except KeyboardInterrupt:
            print("\n\nAnalysis interrupted by user. Progress saved.")
            sys.exit(0)
        except Exception as e:
            print(f"✗ Error running {region_name}: {e}")
            return False
        finally:
            # Clean up temp config
            Path(temp_config).unlink(missing_ok=True)
        
        return True
    
    def run_safe_analysis(self):
        """Run the full analysis with breaks between regions."""
        regions = self.split_config_by_region()
        
        if not regions:
            print("All regions already completed! Delete progress file to restart.")
            return
        
        print(f"Found {len(regions)} regions to process")
        print(f"Already completed: {self.completed_regions}")
        
        for i, (region_name, region_config) in enumerate(regions):
            # Run the region
            success = self.run_region(region_name, region_config)
            
            if not success:
                print(f"Stopping due to error in {region_name}")
                break
            
            # Add break between regions (except for last one)
            if i < len(regions) - 1:
                # Random break between 5-15 minutes
                break_minutes = random.uniform(5, 15)
                print(f"\n⏸ Taking a {break_minutes:.1f} minute break before next region...")
                print(f"Next region: {regions[i+1][0]}")
                print("Press Ctrl+C to stop and save progress\n")
                
                try:
                    time.sleep(break_minutes * 60)
                except KeyboardInterrupt:
                    print("\n\nAnalysis interrupted by user. Progress saved.")
                    break
        
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print(f"Processed regions: {self.completed_regions}")
        print(f"Output saved to: {self.output_base}_*")
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Safe market analysis runner")
    parser.add_argument("config", help="Path to configuration file")
    parser.add_argument("-o", "--output", default="Safe_Analysis", 
                       help="Base name for output directories")
    parser.add_argument("--reset", action="store_true",
                       help="Reset progress and start fresh")
    
    args = parser.parse_args()
    
    if args.reset:
        progress_file = Path(f"{args.output}_progress.txt")
        if progress_file.exists():
            progress_file.unlink()
            print("Progress reset. Starting fresh analysis.")
    
    runner = SafeAnalysisRunner(args.config, args.output)
    runner.run_safe_analysis()

if __name__ == "__main__":
    main()