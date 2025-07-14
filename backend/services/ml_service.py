"""
ML service for AI-driven yield farming optimization.
Provides predictions, strategy recommendations, and model management.
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import os
import joblib
from dataclasses import dataclass
import json

# Import ML modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'ml'))

from models.yield_predictor import YieldPredictor
from models.strategy_selector import StrategySelector
from data.data_collector import DeFiDataCollector
from data.feature_engineering import DeFiFeatureEngineer

logger = logging.getLogger(__name__)

@dataclass
class YieldPrediction:
    """Yield prediction result"""
    protocol: str
    predicted_apy: float
    confidence: float
    prediction_horizon: int  # days
    risk_score: float
    timestamp: datetime

@dataclass
class StrategyRecommendation:
    """Strategy allocation recommendation"""
    allocations: Dict[str, float]  # protocol -> allocation percentage
    expected_apy: float
    risk_score: float
    confidence: float
    rebalance_frequency: int  # hours
    timestamp: datetime

@dataclass
class ModelStatus:
    """Model status information"""
    name: str
    version: str
    last_trained: Optional[datetime]
    accuracy: float
    status: str  # 'active', 'training', 'error'
    error_message: Optional[str] = None

class MLService:
    """Machine learning service for yield optimization"""
    
    def __init__(self):
        self.yield_predictor = None
        self.strategy_selector = None
        self.feature_engineer = DeFiFeatureEngineer()
        self.data_collector = None
        
        # Model paths
        self.model_paths = {
            'yield_predictor': 'ml/models/trained/yield_predictor_latest.h5',
            'strategy_selector': 'ml/models/trained/strategy_selector_latest.h5'
        }
        
        # Model status
        self.model_status = {}
        
        # Prediction cache
        self.prediction_cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Performance metrics
        self.metrics = {
            'predictions_made': 0,
            'recommendations_generated': 0,
            'model_accuracy': {},
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    async def initialize(self):
        """Initialize ML service"""
        try:
            logger.info("Initializing ML service...")
            
            # Load trained models
            await self._load_models()
            
            # Initialize data collector
            self.data_collector = DeFiDataCollector()
            
            # Start background tasks
            asyncio.create_task(self._periodic_model_update())
            asyncio.create_task(self._cache_cleanup())
            
            logger.info("ML service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ML service: {str(e)}")
            raise
    
    async def _load_models(self):
        """Load trained ML models"""
        
        # Load yield predictor
        try:
            if os.path.exists(self.model_paths['yield_predictor']):
                self.yield_predictor = YieldPredictor()
                self.yield_predictor.load_model(self.model_paths['yield_predictor'])
                
                self.model_status['yield_predictor'] = ModelStatus(
                    name='Yield Predictor',
                    version='1.0',
                    last_trained=datetime.fromtimestamp(
                        os.path.getmtime(self.model_paths['yield_predictor'])
                    ),
                    accuracy=0.85,  # Would load from model metadata
                    status='active'
                )
                
                logger.info("Yield predictor model loaded")
            else:
                logger.warning("Yield predictor model not found")
                self.model_status['yield_predictor'] = ModelStatus(
                    name='Yield Predictor',
                    version='1.0',
                    last_trained=None,
                    accuracy=0.0,
                    status='error',
                    error_message='Model file not found'
                )
        except Exception as e:
            logger.error(f"Failed to load yield predictor: {str(e)}")
            self.model_status['yield_predictor'] = ModelStatus(
                name='Yield Predictor',
                version='1.0',
                last_trained=None,
                accuracy=0.0,
                status='error',
                error_message=str(e)
            )
        
        # Load strategy selector
        try:
            if os.path.exists(self.model_paths['strategy_selector']):
                self.strategy_selector = StrategySelector()
                self.strategy_selector.load_model(self.model_paths['strategy_selector'])
                
                self.model_status['strategy_selector'] = ModelStatus(
                    name='Strategy Selector',
                    version='1.0',
                    last_trained=datetime.fromtimestamp(
                        os.path.getmtime(self.model_paths['strategy_selector'])
                    ),
                    accuracy=0.78,  # Would load from model metadata
                    status='active'
                )
                
                logger.info("Strategy selector model loaded")
            else:
                logger.warning("Strategy selector model not found")
                self.model_status['strategy_selector'] = ModelStatus(
                    name='Strategy Selector',
                    version='1.0',
                    last_trained=None,
                    accuracy=0.0,
                    status='error',
                    error_message='Model file not found'
                )
        except Exception as e:
            logger.error(f"Failed to load strategy selector: {str(e)}")
            self.model_status['strategy_selector'] = ModelStatus(
                name='Strategy Selector',
                version='1.0',
                last_trained=None,
                accuracy=0.0,
                status='error',
                error_message=str(e)
            )
    
    async def predict_yields(self, 
                           protocols: List[str],
                           horizon_days: int = 7) -> List[YieldPrediction]:
        """Predict yields for given protocols"""
        
        if not self.yield_predictor:
            raise ValueError("Yield predictor model not available")
        
        # Check cache
        cache_key = f"yields_{'-'.join(protocols)}_{horizon_days}"
        if self._is_cache_valid(cache_key):
            self.metrics['cache_hits'] += 1
            return self.prediction_cache[cache_key]['data']
        
        self.metrics['cache_misses'] += 1
        
        try:
            # Collect recent data
            async with self.data_collector as collector:
                recent_data = await collector.collect_historical_data(days=30)
            
            # Filter for requested protocols
            protocol_data = recent_data[recent_data['protocol'].isin(protocols)]
            
            if protocol_data.empty:
                logger.warning(f"No data found for protocols: {protocols}")
                return []
            
            # Engineer features
            processed_data = self.feature_engineer.engineer_features(
                protocol_data, fit=False
            )
            
            # Make predictions
            predictions_df = self.yield_predictor.predict(processed_data)
            
            # Convert to YieldPrediction objects
            predictions = []
            for _, row in predictions_df.iterrows():
                if row['target'] == f'apy_future_{horizon_days}d':
                    predictions.append(YieldPrediction(
                        protocol=row['protocol'],
                        predicted_apy=row['predicted_value'],
                        confidence=0.8,  # Would calculate actual confidence
                        prediction_horizon=horizon_days,
                        risk_score=self._calculate_risk_score(row['protocol'], processed_data),
                        timestamp=datetime.now()
                    ))
            
            # Cache results
            self.prediction_cache[cache_key] = {
                'data': predictions,
                'timestamp': datetime.now()
            }
            
            self.metrics['predictions_made'] += len(predictions)
            
            logger.info(f"Generated {len(predictions)} yield predictions")
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to predict yields: {str(e)}")
            raise
    
    async def recommend_strategy(self, 
                               user_risk_profile: str,
                               investment_amount: float,
                               available_protocols: List[str]) -> StrategyRecommendation:
        """Generate strategy allocation recommendation"""
        
        if not self.strategy_selector:
            raise ValueError("Strategy selector model not available")
        
        # Check cache
        cache_key = f"strategy_{user_risk_profile}_{investment_amount}_{'-'.join(available_protocols)}"
        if self._is_cache_valid(cache_key):
            self.metrics['cache_hits'] += 1
            return self.prediction_cache[cache_key]['data']
        
        self.metrics['cache_misses'] += 1
        
        try:
            # Collect current market data
            async with self.data_collector as collector:
                current_data = await collector.collect_historical_data(days=7)
            
            # Filter for available protocols
            protocol_data = current_data[current_data['protocol'].isin(available_protocols)]
            
            # Engineer features
            processed_data = self.feature_engineer.engineer_features(
                protocol_data, fit=False
            )
            
            # Get allocation recommendation
            allocation = self.strategy_selector.predict_allocation(processed_data)
            
            # Adjust for risk profile
            adjusted_allocation = self._adjust_for_risk_profile(
                allocation, user_risk_profile
            )
            
            # Calculate expected metrics
            expected_apy = self._calculate_expected_apy(
                adjusted_allocation, processed_data
            )
            risk_score = self._calculate_portfolio_risk(
                adjusted_allocation, processed_data
            )
            
            recommendation = StrategyRecommendation(
                allocations=adjusted_allocation,
                expected_apy=expected_apy,
                risk_score=risk_score,
                confidence=0.75,  # Would calculate actual confidence
                rebalance_frequency=24,  # Daily rebalancing
                timestamp=datetime.now()
            )
            
            # Cache results
            self.prediction_cache[cache_key] = {
                'data': recommendation,
                'timestamp': datetime.now()
            }
            
            self.metrics['recommendations_generated'] += 1
            
            logger.info(f"Generated strategy recommendation with {len(adjusted_allocation)} protocols")
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to generate strategy recommendation: {str(e)}")
            raise
    
    def _adjust_for_risk_profile(self, 
                               allocation: Dict[str, float],
                               risk_profile: str) -> Dict[str, float]:
        """Adjust allocation based on user risk profile"""
        
        risk_multipliers = {
            'conservative': 0.7,
            'moderate': 1.0,
            'aggressive': 1.3
        }
        
        multiplier = risk_multipliers.get(risk_profile, 1.0)
        
        # Adjust allocations (simplified logic)
        adjusted = {}
        total = 0
        
        for protocol, allocation_pct in allocation.items():
            if protocol != 'cash':
                adjusted[protocol] = allocation_pct * multiplier
                total += adjusted[protocol]
        
        # Normalize to 100%
        if total > 0:
            for protocol in adjusted:
                adjusted[protocol] = adjusted[protocol] / total
        
        # Add cash position for conservative profiles
        if risk_profile == 'conservative':
            cash_allocation = 0.2  # 20% cash
            for protocol in adjusted:
                adjusted[protocol] *= (1 - cash_allocation)
            adjusted['cash'] = cash_allocation
        
        return adjusted
    
    def _calculate_expected_apy(self, 
                              allocation: Dict[str, float],
                              data: pd.DataFrame) -> float:
        """Calculate expected portfolio APY"""
        
        expected_apy = 0.0
        
        for protocol, allocation_pct in allocation.items():
            if protocol == 'cash':
                continue  # Cash has 0% APY
            
            protocol_data = data[data['protocol'] == protocol]
            if not protocol_data.empty:
                avg_apy = protocol_data['apy'].mean()
                expected_apy += allocation_pct * avg_apy
        
        return expected_apy
    
    def _calculate_portfolio_risk(self, 
                                allocation: Dict[str, float],
                                data: pd.DataFrame) -> float:
        """Calculate portfolio risk score"""
        
        portfolio_risk = 0.0
        
        for protocol, allocation_pct in allocation.items():
            if protocol == 'cash':
                continue  # Cash has 0 risk
            
            protocol_data = data[data['protocol'] == protocol]
            if not protocol_data.empty:
                avg_risk = protocol_data['risk_score'].mean()
                portfolio_risk += allocation_pct * avg_risk
        
        return portfolio_risk
    
    def _calculate_risk_score(self, protocol: str, data: pd.DataFrame) -> float:
        """Calculate risk score for a protocol"""
        
        protocol_data = data[data['protocol'] == protocol]
        if protocol_data.empty:
            return 50.0  # Default medium risk
        
        return protocol_data['risk_score'].mean()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid"""
        
        if cache_key not in self.prediction_cache:
            return False
        
        cache_entry = self.prediction_cache[cache_key]
        age = datetime.now() - cache_entry['timestamp']
        
        return age.total_seconds() < self.cache_ttl
    
    async def _cache_cleanup(self):
        """Periodic cache cleanup"""
        
        while True:
            try:
                current_time = datetime.now()
                expired_keys = []
                
                for key, entry in self.prediction_cache.items():
                    age = current_time - entry['timestamp']
                    if age.total_seconds() > self.cache_ttl:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.prediction_cache[key]
                
                if expired_keys:
                    logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                
                # Wait 5 minutes before next cleanup
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in cache cleanup: {str(e)}")
                await asyncio.sleep(300)
    
    async def _periodic_model_update(self):
        """Periodic model retraining"""
        
        while True:
            try:
                # Wait 24 hours between updates
                await asyncio.sleep(86400)
                
                logger.info("Starting periodic model update...")
                await self.retrain_models()
                
            except Exception as e:
                logger.error(f"Error in periodic model update: {str(e)}")
    
    async def retrain_models(self):
        """Retrain ML models with latest data"""
        
        try:
            logger.info("Starting model retraining...")
            
            # Update model status
            for model_name in self.model_status:
                self.model_status[model_name].status = 'training'
            
            # Collect training data
            async with self.data_collector as collector:
                training_data = await collector.collect_historical_data(days=90)
            
            # Engineer features
            processed_data = self.feature_engineer.engineer_features(
                training_data, fit=True
            )
            
            # Retrain yield predictor
            if self.yield_predictor:
                yield_results = self.yield_predictor.train(
                    data=processed_data,
                    feature_cols=self.feature_engineer.feature_columns,
                    target_cols=self.feature_engineer.target_columns
                )
                
                # Save updated model
                self.yield_predictor.save_model(self.model_paths['yield_predictor'])
                
                # Update status
                self.model_status['yield_predictor'].status = 'active'
                self.model_status['yield_predictor'].last_trained = datetime.now()
                self.model_status['yield_predictor'].accuracy = yield_results.get('val_metrics', {}).get('r2', 0.0)
            
            # Retrain strategy selector
            if self.strategy_selector:
                strategy_results = self.strategy_selector.train(
                    data=processed_data,
                    episodes=500  # Reduced for periodic updates
                )
                
                # Save updated model
                self.strategy_selector.save_model(self.model_paths['strategy_selector'])
                
                # Update status
                self.model_status['strategy_selector'].status = 'active'
                self.model_status['strategy_selector'].last_trained = datetime.now()
                self.model_status['strategy_selector'].accuracy = strategy_results.get('avg_reward', 0.0)
            
            logger.info("Model retraining completed successfully")
            
        except Exception as e:
            logger.error(f"Model retraining failed: {str(e)}")
            
            # Update error status
            for model_name in self.model_status:
                self.model_status[model_name].status = 'error'
                self.model_status[model_name].error_message = str(e)
    
    async def collect_training_data(self):
        """Collect new training data"""
        
        try:
            logger.info("Collecting training data...")
            
            async with self.data_collector as collector:
                new_data = await collector.collect_historical_data(days=7)
                
                # Save to training dataset
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                await collector.save_data(new_data, f"training_data_{timestamp}.csv")
            
            logger.info("Training data collection completed")
            
        except Exception as e:
            logger.error(f"Training data collection failed: {str(e)}")
            raise
    
    async def get_model_status(self) -> Dict[str, ModelStatus]:
        """Get status of all models"""
        return self.model_status
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get ML service metrics"""
        
        return {
            'models_loaded': len([
                status for status in self.model_status.values() 
                if status.status == 'active'
            ]),
            'cache_size': len(self.prediction_cache),
            'cache_hit_rate': (
                self.metrics['cache_hits'] / 
                (self.metrics['cache_hits'] + self.metrics['cache_misses'])
                if (self.metrics['cache_hits'] + self.metrics['cache_misses']) > 0 else 0
            ),
            'performance': self.metrics,
            'model_status': {
                name: {
                    'status': status.status,
                    'accuracy': status.accuracy,
                    'last_trained': status.last_trained.isoformat() if status.last_trained else None
                }
                for name, status in self.model_status.items()
            }
        }
    
    async def cleanup(self):
        """Cleanup ML service"""
        logger.info("Cleaning up ML service...")
        
        # Clear cache
        self.prediction_cache.clear()
        
        # Save metrics
        # Cancel background tasks
