"""Market compensation visualization module with Tufte-style comparison charts."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import pandas as pd


class CompensationBandVisualizer:
    """Creates market compensation comparison visualizations."""
    
    # Minimal color palette
    COLORS = {
        'payband_fill': '#e8f4ea',     # Very light green
        'payband_edge': '#4a9b5c',     # Darker green  
        'market_box': '#d3d3d3',       # Light gray
        'market_edge': '#333333',      # Dark gray
        'median_line': '#000000',      # Black
        'whisker': '#666666',          # Medium gray
        'text_red': '#d9534f',         # Red for above band
        'text_green': '#5cb85c',       # Green for within band
        'text_gray': '#666666',        # Gray for labels
        'background': 'white'
    }
    
    def __init__(self, output_dir: str):
        """Initialize visualizer with output directory.
        
        Args:
            output_dir: Directory to save charts
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create charts subdirectory
        self.charts_dir = self.output_dir / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate_market_paybands(
        self, 
        config: Dict, 
        region_name: str, 
        role_id: str
    ) -> Dict[str, Tuple[float, float]]:
        """
        Aggregate center-level paybands to market-level statistics.
        
        Returns dict of market_name -> (min, max) tuples
        """
        market_paybands = {}
        
        # Find the region
        region = None
        for r in config.get('regions', []):
            if r['name'] == region_name:
                region = r
                break
        
        if not region:
            return market_paybands
        
        # Aggregate by market
        for market in region.get('markets', []):
            market_name = market['name']
            paybands = []
            
            # Collect all center paybands for this role
            for center in market.get('centers', []):
                if 'paybands' in center and role_id in center['paybands']:
                    pb = center['paybands'][role_id]
                    paybands.append((pb['min'], pb['max']))
            
            if paybands:
                # Calculate market-level statistics
                mins = [pb[0] for pb in paybands]
                maxs = [pb[1] for pb in paybands]
                
                market_min = min(mins)
                market_max = max(maxs)
                
                market_paybands[market_name] = (market_min, market_max)
        
        return market_paybands
    
    def create_market_comparison_chart(
        self,
        market_name: str,
        role_name: str,
        role_type: str,
        our_payband: Tuple[float, float],
        market_stats: Dict[str, float],
        sample_size: int,
        output_filename: Optional[str] = None
    ) -> Path:
        """
        Create a Tufte-style market comparison chart.
        
        Args:
            market_name: Name of the market
            role_name: Display name of the role
            role_type: 'hourly' or 'salary'
            our_payband: Tuple of (min, max) for our payband
            market_stats: Dict with 'min', 'p25', 'median', 'p75', 'max' from actual job data
            sample_size: Number of salaries in the market data
            output_filename: Optional custom filename
        
        Returns:
            Path to the generated chart
        """
        # Setup figure with minimal style
        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor(self.COLORS['background'])
        ax.set_facecolor(self.COLORS['background'])
        
        y_position = 0
        
        # 1. Our payband as reference area (subtle background)
        if our_payband:
            band_rect = plt.Rectangle(
                (our_payband[0], y_position - 0.3),
                our_payband[1] - our_payband[0],
                0.6,
                facecolor=self.COLORS['payband_fill'],
                edgecolor=self.COLORS['payband_edge'],
                linewidth=1,
                linestyle='--',
                alpha=0.5,
                zorder=1,
                label='Our Payband'
            )
            ax.add_patch(band_rect)
        
        # 2. Market data as box plot elements
        # Box for IQR (25th to 75th percentile)
        if 'p25' in market_stats and 'p75' in market_stats:
            market_box = plt.Rectangle(
                (market_stats['p25'], y_position - 0.15),
                market_stats['p75'] - market_stats['p25'],
                0.3,
                facecolor=self.COLORS['market_box'],
                edgecolor=self.COLORS['market_edge'],
                linewidth=2,
                zorder=3
            )
            ax.add_patch(market_box)
        
        # Median line (bold)
        if 'median' in market_stats:
            ax.plot([market_stats['median'], market_stats['median']], 
                   [y_position - 0.15, y_position + 0.15],
                   color=self.COLORS['median_line'],
                   linewidth=3,
                   zorder=4)
            
            # Check if median is within our band
            if our_payband:
                within_band = our_payband[0] <= market_stats['median'] <= our_payband[1]
                
                # Add median value label with indicator
                if role_type == 'salary':
                    median_label = f"Market Median: ${market_stats['median']/1000:.0f}K"
                else:
                    median_label = f"Market Median: ${market_stats['median']:.0f}/hr"
                    
                if not within_band:
                    if market_stats['median'] > our_payband[1]:
                        gap = market_stats['median'] - our_payband[1]
                        if role_type == 'salary':
                            median_label += f" (${gap/1000:.1f}K above band)"
                        else:
                            median_label += f" (${gap:.1f}/hr above band)"
                        label_color = self.COLORS['text_red']
                    else:
                        gap = our_payband[0] - market_stats['median']
                        if role_type == 'salary':
                            median_label += f" (${gap/1000:.1f}K below band)"
                        else:
                            median_label += f" (${gap:.1f}/hr below band)"
                        label_color = self.COLORS['text_green']
                else:
                    median_label += " (within band)"
                    label_color = self.COLORS['text_green']
            else:
                if role_type == 'salary':
                    median_label = f"Market Median: ${market_stats['median']/1000:.0f}K"
                else:
                    median_label = f"Market Median: ${market_stats['median']:.0f}/hr"
                label_color = self.COLORS['text_gray']
            
            ax.text(market_stats['median'], y_position + 0.35, median_label,
                   ha='center', va='bottom', fontsize=11, fontweight='bold',
                   color=label_color, zorder=5)
        
        # Whiskers (min to max)
        if 'min' in market_stats and 'max' in market_stats:
            # Min whisker
            ax.plot([market_stats['min'], market_stats.get('p25', market_stats['min'])],
                   [y_position, y_position],
                   color=self.COLORS['whisker'],
                   linewidth=1,
                   zorder=2)
            ax.plot([market_stats['min'], market_stats['min']],
                   [y_position - 0.1, y_position + 0.1],
                   color=self.COLORS['whisker'],
                   linewidth=1,
                   zorder=2)
            
            # Max whisker
            ax.plot([market_stats.get('p75', market_stats['max']), market_stats['max']],
                   [y_position, y_position],
                   color=self.COLORS['whisker'],
                   linewidth=1,
                   zorder=2)
            ax.plot([market_stats['max'], market_stats['max']],
                   [y_position - 0.1, y_position + 0.1],
                   color=self.COLORS['whisker'],
                   linewidth=1,
                   zorder=2)
        
        # 3. Add our band boundaries as reference lines
        if our_payband:
            ax.axvline(our_payband[0], color=self.COLORS['payband_edge'], 
                      linestyle=':', alpha=0.7, linewidth=1)
            ax.axvline(our_payband[1], color=self.COLORS['payband_edge'], 
                      linestyle=':', alpha=0.7, linewidth=1)
            
            # Our band labels
            if role_type == 'salary':
                ax.text(our_payband[0], y_position - 0.45, f"${our_payband[0]/1000:.0f}K",
                       ha='center', va='top', fontsize=9, color=self.COLORS['payband_edge'], 
                       style='italic')
                ax.text(our_payband[1], y_position - 0.45, f"${our_payband[1]/1000:.0f}K",
                       ha='center', va='top', fontsize=9, color=self.COLORS['payband_edge'], 
                       style='italic')
            else:
                ax.text(our_payband[0], y_position - 0.45, f"${our_payband[0]:.0f}",
                       ha='center', va='top', fontsize=9, color=self.COLORS['payband_edge'], 
                       style='italic')
                ax.text(our_payband[1], y_position - 0.45, f"${our_payband[1]:.0f}",
                       ha='center', va='top', fontsize=9, color=self.COLORS['payband_edge'], 
                       style='italic')
        
        # Sample size indicator
        ax.text(0.02, 0.98, f"n={sample_size} market salaries",
               transform=ax.transAxes, fontsize=9, color=self.COLORS['text_gray'],
               va='top', ha='left', style='italic')
        
        # Title and labels
        ax.set_title(f"{role_name} Market Compensation vs. Our Payband",
                    fontsize=14, fontweight='bold', pad=20)
        ax.text(0.5, -0.15, f"{market_name}",
               transform=ax.transAxes, fontsize=11, color=self.COLORS['text_gray'],
               va='top', ha='center', style='italic')
        
        if role_type == 'salary':
            ax.set_xlabel('Annual Compensation', fontsize=11)
        else:
            ax.set_xlabel('Hourly Rate', fontsize=11)
        
        # Remove y-axis
        ax.set_ylim(-0.6, 0.6)
        ax.set_yticks([])
        
        # Minimal x-axis
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_linewidth(0.5)
        
        # Format x-axis
        if role_type == 'salary':
            # Format as $XXK for salaries
            ax.set_xticks(ax.get_xticks())
            ax.set_xticklabels([f"${x/1000:.0f}K" for x in ax.get_xticks()], fontsize=10)
        else:
            # Format as $XX for hourly
            ax.set_xticks(ax.get_xticks())
            ax.set_xticklabels([f"${x:.0f}" for x in ax.get_xticks()], fontsize=10)
        
        # Minimal grid
        ax.grid(True, axis='x', alpha=0.2, linestyle=':', color='#cccccc')
        ax.set_axisbelow(True)
        
        # Legend
        legend_elements = []
        if our_payband:
            legend_elements.append(
                plt.Rectangle((0, 0), 1, 1, facecolor=self.COLORS['payband_fill'], 
                             edgecolor=self.COLORS['payband_edge'], 
                             linewidth=1, linestyle='--', label='Our Payband')
            )
        legend_elements.extend([
            plt.Rectangle((0, 0), 1, 1, facecolor=self.COLORS['market_box'], 
                         edgecolor=self.COLORS['market_edge'],
                         linewidth=2, label='Market IQR (25th-75th %ile)'),
            plt.Line2D([0], [0], color=self.COLORS['median_line'], 
                      linewidth=3, label='Market Median')
        ])
        ax.legend(handles=legend_elements, loc='upper right', frameon=False, fontsize=9)
        
        plt.tight_layout()
        
        # Save figure
        if not output_filename:
            safe_market = market_name.replace(' ', '_').replace('/', '-')
            safe_role = role_name.replace(' ', '_').replace('/', '-')
            output_filename = f"{safe_market}_{safe_role}_market_comparison.png"
        
        output_path = self.charts_dir / output_filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=self.COLORS['background'])
        plt.close()
        
        return output_path
    
    def generate_all_charts(self, config: Dict, aggregated_markets: Dict = None) -> List[Path]:
        """
        Generate compensation charts for all regions and roles using actual market data.
        
        Args:
            config: YAML configuration dictionary
            aggregated_markets: Market data from actual job searches
        
        Returns:
            List of paths to generated charts
        """
        generated_charts = []
        
        if not aggregated_markets:
            return generated_charts
        
        # Get role definitions
        roles = {}
        for role in config.get('roles', []):
            roles[role['id']] = {
                'name': role['name'],
                'pay_type': role['pay_type']
            }
        
        # Process each region
        for region in config.get('regions', []):
            region_name = region['name']
            
            # Get paybands for this region
            for role_id, role_info in roles.items():
                market_paybands = self.aggregate_market_paybands(config, region_name, role_id)
                
                # Process each market with data
                for market_name, market_data in aggregated_markets.items():
                    # Check if this market has role-specific data
                    if hasattr(market_data, 'role_data') and market_data.role_data:
                        if role_id in market_data.role_data:
                            role_data = market_data.role_data[role_id]
                            
                            # Only create chart if we have sufficient data
                            if role_data.has_sufficient_data and not role_data.salary_data.empty:
                                # Calculate market statistics
                                salaries = role_data.salary_data['salary'].values
                                market_stats = {
                                    'min': np.min(salaries),
                                    'p25': np.percentile(salaries, 25),
                                    'median': np.median(salaries),
                                    'p75': np.percentile(salaries, 75),
                                    'max': np.max(salaries)
                                }
                                
                                # Get our payband for this market
                                our_payband = market_paybands.get(market_name)
                                
                                # Create comparison chart
                                chart_path = self.create_market_comparison_chart(
                                    market_name=market_name,
                                    role_name=role_info['name'],
                                    role_type=role_info['pay_type'],
                                    our_payband=our_payband,
                                    market_stats=market_stats,
                                    sample_size=len(salaries),
                                    output_filename=None
                                )
                                
                                if chart_path:
                                    generated_charts.append(chart_path)
                                    print(f"  Generated: {chart_path.name}")
        
        return generated_charts