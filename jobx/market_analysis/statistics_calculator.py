"""Statistical calculator for compensation analysis."""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from scipy import stats
from dataclasses import dataclass


@dataclass
class CompensationStatistics:
    """Container for compensation statistics."""
    # Descriptive statistics
    mean: float
    median: float
    mode: Optional[float]
    min_value: float
    max_value: float
    range_value: float
    std_dev: float
    coeff_variation: float
    
    # Percentiles
    p10: float
    p25: float
    p50: float  # Same as median
    p75: float
    p90: float
    iqr: float
    
    # Distribution shape
    skewness: float
    kurtosis: float
    
    # Data quality
    sample_size: int
    sufficient_data: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary."""
        return {
            'mean': round(self.mean, 2),
            'median': round(self.median, 2),
            'mode': round(self.mode, 2) if self.mode else None,
            'min': round(self.min_value, 2),
            'max': round(self.max_value, 2),
            'range': round(self.range_value, 2),
            'std_dev': round(self.std_dev, 2),
            'coeff_variation': round(self.coeff_variation, 4),
            'p10': round(self.p10, 2),
            'p25': round(self.p25, 2),
            'p50': round(self.p50, 2),
            'p75': round(self.p75, 2),
            'p90': round(self.p90, 2),
            'iqr': round(self.iqr, 2),
            'skewness': round(self.skewness, 4),
            'kurtosis': round(self.kurtosis, 4),
            'sample_size': self.sample_size,
            'sufficient_data': self.sufficient_data
        }


class StatisticsCalculator:
    """Calculates comprehensive statistics for compensation data."""
    
    def __init__(self, min_sample_size: int = 100):
        """Initialize statistics calculator.
        
        Args:
            min_sample_size: Minimum sample size for sufficient data
        """
        self.min_sample_size = min_sample_size
    
    def calculate_statistics(self, salary_data: pd.DataFrame) -> Optional[CompensationStatistics]:
        """Calculate all statistics for salary data.
        
        Args:
            salary_data: DataFrame with 'salary' column
            
        Returns:
            CompensationStatistics object or None if no data
        """
        if salary_data.empty or 'salary' not in salary_data.columns:
            return None
        
        salaries = salary_data['salary'].values
        sample_size = len(salaries)
        
        if sample_size == 0:
            return None
        
        # Calculate descriptive statistics
        mean = np.mean(salaries)
        median = np.median(salaries)
        mode = self._calculate_mode(salaries)
        min_value = np.min(salaries)
        max_value = np.max(salaries)
        range_value = max_value - min_value
        std_dev = np.std(salaries)
        coeff_variation = std_dev / mean if mean != 0 else 0
        
        # Calculate percentiles
        percentiles = np.percentile(salaries, [10, 25, 50, 75, 90])
        p10, p25, p50, p75, p90 = percentiles
        iqr = p75 - p25
        
        # Calculate distribution shape
        skewness = self._safe_skewness(salaries)
        kurtosis_val = self._safe_kurtosis(salaries)
        
        # Determine data sufficiency
        sufficient_data = sample_size >= self.min_sample_size
        
        return CompensationStatistics(
            mean=mean,
            median=median,
            mode=mode,
            min_value=min_value,
            max_value=max_value,
            range_value=range_value,
            std_dev=std_dev,
            coeff_variation=coeff_variation,
            p10=p10,
            p25=p25,
            p50=p50,
            p75=p75,
            p90=p90,
            iqr=iqr,
            skewness=skewness,
            kurtosis=kurtosis_val,
            sample_size=sample_size,
            sufficient_data=sufficient_data
        )
    
    def _calculate_mode(self, salaries: np.ndarray) -> Optional[float]:
        """Calculate mode with proper handling of continuous data.
        
        Args:
            salaries: Array of salary values
            
        Returns:
            Mode value or None if no clear mode
        """
        try:
            # Round salaries to nearest 1000 for mode calculation
            rounded = np.round(salaries / 1000) * 1000
            mode_result = stats.mode(rounded, keepdims=False)
            
            # Only return mode if it appears more than once
            if mode_result.count > 1:
                return float(mode_result.mode)
            return None
        except:
            return None
    
    def _safe_skewness(self, salaries: np.ndarray) -> float:
        """Calculate skewness with error handling.
        
        Args:
            salaries: Array of salary values
            
        Returns:
            Skewness value or 0 if calculation fails
        """
        try:
            if len(salaries) < 3:
                return 0.0
            return float(stats.skew(salaries))
        except:
            return 0.0
    
    def _safe_kurtosis(self, salaries: np.ndarray) -> float:
        """Calculate kurtosis with error handling.
        
        Args:
            salaries: Array of salary values
            
        Returns:
            Kurtosis value or 0 if calculation fails
        """
        try:
            if len(salaries) < 4:
                return 0.0
            return float(stats.kurtosis(salaries))
        except:
            return 0.0
    
    def calculate_market_comparison(self, 
                                   market_stats: Dict[str, CompensationStatistics]) -> pd.DataFrame:
        """Create comparison table across markets.
        
        Args:
            market_stats: Dictionary mapping market names to statistics
            
        Returns:
            DataFrame with market comparison
        """
        if not market_stats:
            return pd.DataFrame()
        
        comparison_data = []
        for market_name, stats in market_stats.items():
            if stats:
                row = {
                    'Market': market_name,
                    'Sample Size': stats.sample_size,
                    'Mean': stats.mean,
                    'Median': stats.median,
                    'P25': stats.p25,
                    'P75': stats.p75,
                    'P90': stats.p90,
                    'IQR': stats.iqr,
                    'Std Dev': stats.std_dev,
                    'Skewness': stats.skewness,
                    'Sufficient Data': stats.sufficient_data
                }
                comparison_data.append(row)
        
        df = pd.DataFrame(comparison_data)
        
        # Sort by median salary descending
        if not df.empty and 'Median' in df.columns:
            df = df.sort_values('Median', ascending=False)
        
        return df
    
    def interpret_statistics(self, stats: CompensationStatistics) -> Dict[str, str]:
        """Provide interpretation of statistics.
        
        Args:
            stats: Calculated statistics
            
        Returns:
            Dictionary with interpretations
        """
        interpretations = {}
        
        # Interpret skewness
        if stats.skewness > 0.5:
            interpretations['distribution'] = "Right-skewed (long tail of high salaries)"
        elif stats.skewness < -0.5:
            interpretations['distribution'] = "Left-skewed (long tail of low salaries)"
        else:
            interpretations['distribution'] = "Approximately symmetric"
        
        # Interpret spread
        if stats.coeff_variation < 0.15:
            interpretations['spread'] = "Low variation (compressed salary range)"
        elif stats.coeff_variation > 0.30:
            interpretations['spread'] = "High variation (wide salary range)"
        else:
            interpretations['spread'] = "Moderate variation"
        
        # Interpret kurtosis
        if stats.kurtosis > 1:
            interpretations['tails'] = "Heavy tails (more extreme salaries)"
        elif stats.kurtosis < -1:
            interpretations['tails'] = "Light tails (fewer extreme salaries)"
        else:
            interpretations['tails'] = "Normal tail behavior"
        
        # Market positioning
        salary_bands = {
            'Entry Level': (stats.p10, stats.p25),
            'Mid Level': (stats.p25, stats.p75),
            'Senior Level': (stats.p75, stats.p90),
            'Top Tier': (stats.p90, stats.max_value)
        }
        
        band_text = []
        for level, (low, high) in salary_bands.items():
            band_text.append(f"{level}: ${low:,.0f} - ${high:,.0f}")
        interpretations['salary_bands'] = "; ".join(band_text)
        
        return interpretations