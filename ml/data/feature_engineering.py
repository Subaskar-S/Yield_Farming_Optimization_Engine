"""
Feature engineering module for DeFi yield farming optimization.
Creates features for machine learning models from raw DeFi data.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import ta
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DeFiFeatureEngineer:
    """Feature engineering for DeFi yield farming data"""
    
    def __init__(self):
        self.scalers = {}
        self.feature_columns = []
        self.target_columns = []
        
    def create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create time-based features"""
        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Time-based features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['day_of_month'] = df['timestamp'].dt.day
        df['month'] = df['timestamp'].dt.month
        df['quarter'] = df['timestamp'].dt.quarter
        
        # Cyclical encoding for time features
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        return df
    
    def create_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create technical analysis indicators"""
        df = df.copy()
        df = df.sort_values(['protocol', 'timestamp'])
        
        # Group by protocol to calculate indicators
        for protocol in df['protocol'].unique():
            mask = df['protocol'] == protocol
            protocol_data = df[mask].copy()
            
            if len(protocol_data) < 20:  # Need minimum data for indicators
                continue
                
            # Moving averages
            protocol_data['apy_ma_7'] = protocol_data['apy'].rolling(window=7, min_periods=1).mean()
            protocol_data['apy_ma_30'] = protocol_data['apy'].rolling(window=30, min_periods=1).mean()
            protocol_data['tvl_ma_7'] = protocol_data['tvl'].rolling(window=7, min_periods=1).mean()
            protocol_data['tvl_ma_30'] = protocol_data['tvl'].rolling(window=30, min_periods=1).mean()
            
            # Volatility indicators
            protocol_data['apy_volatility_7'] = protocol_data['apy'].rolling(window=7, min_periods=1).std()
            protocol_data['apy_volatility_30'] = protocol_data['apy'].rolling(window=30, min_periods=1).std()
            
            # RSI (Relative Strength Index)
            if len(protocol_data) >= 14:
                protocol_data['apy_rsi'] = ta.momentum.RSIIndicator(
                    protocol_data['apy'], window=14
                ).rsi()
            
            # Bollinger Bands
            if len(protocol_data) >= 20:
                bb_indicator = ta.volatility.BollingerBands(
                    protocol_data['apy'], window=20, window_dev=2
                )
                protocol_data['apy_bb_upper'] = bb_indicator.bollinger_hband()
                protocol_data['apy_bb_lower'] = bb_indicator.bollinger_lband()
                protocol_data['apy_bb_middle'] = bb_indicator.bollinger_mavg()
                protocol_data['apy_bb_width'] = (
                    protocol_data['apy_bb_upper'] - protocol_data['apy_bb_lower']
                ) / protocol_data['apy_bb_middle']
            
            # MACD
            if len(protocol_data) >= 26:
                macd_indicator = ta.trend.MACD(protocol_data['apy'])
                protocol_data['apy_macd'] = macd_indicator.macd()
                protocol_data['apy_macd_signal'] = macd_indicator.macd_signal()
                protocol_data['apy_macd_histogram'] = macd_indicator.macd_diff()
            
            # Update main dataframe
            df.loc[mask] = protocol_data
        
        return df
    
    def create_market_features(self, df: pd.DataFrame, market_data: pd.DataFrame = None) -> pd.DataFrame:
        """Create market-related features"""
        df = df.copy()
        
        # TVL-based features
        df['tvl_log'] = np.log1p(df['tvl'])
        df['tvl_rank'] = df.groupby('timestamp')['tvl'].rank(pct=True)
        
        # APY-based features
        df['apy_rank'] = df.groupby('timestamp')['apy'].rank(pct=True)
        df['apy_zscore'] = df.groupby('timestamp')['apy'].transform(
            lambda x: (x - x.mean()) / x.std()
        )
        
        # Risk-adjusted returns
        df['risk_adjusted_apy'] = df['apy'] / (df['risk_score'] + 1)
        df['sharpe_ratio'] = df['apy'] / (df['apy_volatility_7'] + 0.01)
        
        # Liquidity features
        df['liquidity_ratio'] = df['liquidity_depth'] / (df['tvl'] + 1)
        df['utilization_rate'] = (df['tvl'] - df['liquidity_depth']) / (df['tvl'] + 1)
        
        # Competition features
        df['protocol_count'] = df.groupby('timestamp')['protocol'].transform('count')
        df['market_share'] = df['tvl'] / df.groupby('timestamp')['tvl'].transform('sum')
        
        return df
    
    def create_lag_features(self, df: pd.DataFrame, lags: List[int] = [1, 3, 7, 14]) -> pd.DataFrame:
        """Create lagged features"""
        df = df.copy()
        df = df.sort_values(['protocol', 'timestamp'])
        
        lag_columns = ['apy', 'tvl', 'risk_score', 'liquidity_depth']
        
        for protocol in df['protocol'].unique():
            mask = df['protocol'] == protocol
            protocol_data = df[mask].copy()
            
            for col in lag_columns:
                for lag in lags:
                    protocol_data[f'{col}_lag_{lag}'] = protocol_data[col].shift(lag)
            
            df.loc[mask] = protocol_data
        
        return df
    
    def create_change_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create change/difference features"""
        df = df.copy()
        df = df.sort_values(['protocol', 'timestamp'])
        
        change_columns = ['apy', 'tvl', 'risk_score', 'liquidity_depth']
        
        for protocol in df['protocol'].unique():
            mask = df['protocol'] == protocol
            protocol_data = df[mask].copy()
            
            for col in change_columns:
                # Absolute changes
                protocol_data[f'{col}_change_1d'] = protocol_data[col].diff(1)
                protocol_data[f'{col}_change_7d'] = protocol_data[col].diff(7)
                
                # Percentage changes
                protocol_data[f'{col}_pct_change_1d'] = protocol_data[col].pct_change(1)
                protocol_data[f'{col}_pct_change_7d'] = protocol_data[col].pct_change(7)
            
            df.loc[mask] = protocol_data
        
        return df
    
    def create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features between variables"""
        df = df.copy()
        
        # APY and risk interactions
        df['apy_risk_interaction'] = df['apy'] * df['risk_score']
        df['apy_tvl_interaction'] = df['apy'] * np.log1p(df['tvl'])
        
        # TVL and liquidity interactions
        df['tvl_liquidity_ratio'] = df['tvl'] / (df['liquidity_depth'] + 1)
        df['liquidity_efficiency'] = df['apy'] / (df['liquidity_depth'] + 1)
        
        # Time-based interactions
        df['weekend_effect'] = (df['day_of_week'] >= 5).astype(int) * df['apy']
        df['month_end_effect'] = (df['day_of_month'] >= 28).astype(int) * df['apy']
        
        return df
    
    def create_protocol_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create protocol-specific features"""
        df = df.copy()
        
        # Protocol encoding
        protocol_dummies = pd.get_dummies(df['protocol'], prefix='protocol')
        df = pd.concat([df, protocol_dummies], axis=1)
        
        # Protocol statistics
        protocol_stats = df.groupby('protocol').agg({
            'apy': ['mean', 'std', 'min', 'max'],
            'tvl': ['mean', 'std'],
            'risk_score': ['mean', 'std']
        }).round(4)
        
        protocol_stats.columns = ['_'.join(col).strip() for col in protocol_stats.columns]
        protocol_stats = protocol_stats.add_prefix('protocol_')
        
        # Merge protocol statistics
        df = df.merge(protocol_stats, left_on='protocol', right_index=True, how='left')
        
        return df
    
    def create_target_variables(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create target variables for prediction"""
        df = df.copy()
        df = df.sort_values(['protocol', 'timestamp'])
        
        # Future APY prediction targets
        for protocol in df['protocol'].unique():
            mask = df['protocol'] == protocol
            protocol_data = df[mask].copy()
            
            # Future APY values
            protocol_data['apy_future_1d'] = protocol_data['apy'].shift(-1)
            protocol_data['apy_future_3d'] = protocol_data['apy'].shift(-3)
            protocol_data['apy_future_7d'] = protocol_data['apy'].shift(-7)
            
            # Future APY changes
            protocol_data['apy_change_future_1d'] = (
                protocol_data['apy_future_1d'] - protocol_data['apy']
            )
            protocol_data['apy_change_future_7d'] = (
                protocol_data['apy_future_7d'] - protocol_data['apy']
            )
            
            # Binary classification targets
            protocol_data['apy_increase_1d'] = (
                protocol_data['apy_change_future_1d'] > 0
            ).astype(int)
            protocol_data['apy_increase_7d'] = (
                protocol_data['apy_change_future_7d'] > 0
            ).astype(int)
            
            df.loc[mask] = protocol_data
        
        return df
    
    def scale_features(self, df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        """Scale numerical features"""
        df = df.copy()
        
        # Identify numerical columns to scale
        numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Exclude target variables and identifiers
        exclude_cols = [
            'timestamp', 'apy_future_1d', 'apy_future_3d', 'apy_future_7d',
            'apy_change_future_1d', 'apy_change_future_7d',
            'apy_increase_1d', 'apy_increase_7d'
        ]
        
        scale_cols = [col for col in numerical_cols if col not in exclude_cols]
        
        if fit:
            self.scalers['standard'] = StandardScaler()
            df[scale_cols] = self.scalers['standard'].fit_transform(df[scale_cols])
        else:
            if 'standard' in self.scalers:
                df[scale_cols] = self.scalers['standard'].transform(df[scale_cols])
        
        return df
    
    def engineer_features(self, df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        """Main feature engineering pipeline"""
        logger.info("Starting feature engineering pipeline...")
        
        # Create time features
        df = self.create_time_features(df)
        logger.info("Created time features")
        
        # Create technical indicators
        df = self.create_technical_indicators(df)
        logger.info("Created technical indicators")
        
        # Create market features
        df = self.create_market_features(df)
        logger.info("Created market features")
        
        # Create lag features
        df = self.create_lag_features(df)
        logger.info("Created lag features")
        
        # Create change features
        df = self.create_change_features(df)
        logger.info("Created change features")
        
        # Create interaction features
        df = self.create_interaction_features(df)
        logger.info("Created interaction features")
        
        # Create protocol features
        df = self.create_protocol_features(df)
        logger.info("Created protocol features")
        
        # Create target variables
        df = self.create_target_variables(df)
        logger.info("Created target variables")
        
        # Scale features
        df = self.scale_features(df, fit=fit)
        logger.info("Scaled features")
        
        # Store feature columns
        if fit:
            self.feature_columns = [
                col for col in df.columns 
                if col not in ['timestamp', 'protocol', 'address'] and 
                not col.startswith('apy_future') and 
                not col.startswith('apy_change_future') and 
                not col.startswith('apy_increase')
            ]
            
            self.target_columns = [
                'apy_future_1d', 'apy_future_7d', 
                'apy_change_future_1d', 'apy_change_future_7d',
                'apy_increase_1d', 'apy_increase_7d'
            ]
        
        logger.info(f"Feature engineering complete. Created {len(self.feature_columns)} features")
        return df
    
    def get_feature_importance_data(self, df: pd.DataFrame) -> Dict:
        """Prepare data for feature importance analysis"""
        return {
            'features': self.feature_columns,
            'targets': self.target_columns,
            'feature_data': df[self.feature_columns],
            'target_data': df[self.target_columns]
        }
