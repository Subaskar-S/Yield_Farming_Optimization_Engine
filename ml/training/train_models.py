"""
Main training pipeline for AI-driven yield farming optimization models.
Orchestrates data collection, feature engineering, and model training.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os
import json
import argparse
from typing import Dict, List, Any

# Import our modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from data.data_collector import DeFiDataCollector
from data.feature_engineering import DeFiFeatureEngineer
from models.yield_predictor import YieldPredictor
from models.strategy_selector import StrategySelector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ml/logs/training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ModelTrainingPipeline:
    """Main pipeline for training all ML models"""
    
    def __init__(self, config_path: str = "ml/config/training_config.json"):
        self.config = self._load_config(config_path)
        self.data_collector = None
        self.feature_engineer = DeFiFeatureEngineer()
        self.yield_predictor = None
        self.strategy_selector = None
        
        # Create necessary directories
        self._create_directories()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load training configuration"""
        default_config = {
            "data_collection": {
                "historical_days": 90,
                "protocols": ["compound", "aave", "yearn"],
                "tokens": ["USDC", "USDT", "DAI", "ETH", "WBTC"],
                "update_interval": 3600
            },
            "feature_engineering": {
                "sequence_length": 30,
                "lag_periods": [1, 3, 7, 14],
                "technical_indicators": True,
                "market_features": True
            },
            "yield_predictor": {
                "sequence_length": 30,
                "prediction_horizon": 7,
                "lstm_units": [128, 64, 32],
                "dropout_rate": 0.2,
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100,
                "validation_split": 0.2
            },
            "strategy_selector": {
                "episodes": 1000,
                "learning_rate": 0.001,
                "epsilon_decay": 0.995,
                "memory_size": 10000,
                "batch_size": 32
            },
            "output": {
                "model_dir": "ml/models/trained",
                "data_dir": "ml/data/processed",
                "results_dir": "ml/results"
            }
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                # Merge with defaults
                for key, value in loaded_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        
        return default_config
    
    def _create_directories(self):
        """Create necessary directories"""
        directories = [
            "ml/logs",
            "ml/data/raw",
            "ml/data/processed",
            "ml/models/trained",
            "ml/models/checkpoints",
            "ml/results",
            "ml/config"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    async def collect_data(self) -> pd.DataFrame:
        """Collect historical DeFi data"""
        logger.info("Starting data collection...")
        
        async with DeFiDataCollector() as collector:
            # Collect historical data
            historical_data = await collector.collect_historical_data(
                days=self.config["data_collection"]["historical_days"]
            )
            
            # Save raw data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_data_path = f"ml/data/raw/defi_data_{timestamp}.csv"
            await collector.save_data(historical_data, f"defi_data_{timestamp}.csv")
            
            logger.info(f"Collected {len(historical_data)} data points")
            return historical_data
    
    def engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engineer features for machine learning"""
        logger.info("Starting feature engineering...")
        
        # Apply feature engineering pipeline
        processed_data = self.feature_engineer.engineer_features(data, fit=True)
        
        # Save processed data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_data_path = f"ml/data/processed/processed_data_{timestamp}.csv"
        processed_data.to_csv(processed_data_path, index=False)
        
        logger.info(f"Feature engineering complete. Created {len(self.feature_engineer.feature_columns)} features")
        return processed_data
    
    def train_yield_predictor(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Train the yield prediction model"""
        logger.info("Training yield prediction model...")
        
        # Initialize model
        self.yield_predictor = YieldPredictor(
            sequence_length=self.config["yield_predictor"]["sequence_length"],
            prediction_horizon=self.config["yield_predictor"]["prediction_horizon"],
            model_config=self.config["yield_predictor"]
        )
        
        # Prepare data
        feature_cols = self.feature_engineer.feature_columns
        target_cols = [col for col in self.feature_engineer.target_columns 
                      if col in data.columns and not data[col].isna().all()]
        
        if not target_cols:
            logger.error("No valid target columns found")
            return {}
        
        # Split data for training and validation
        split_date = data['timestamp'].quantile(0.8)
        train_data = data[data['timestamp'] <= split_date]
        val_data = data[data['timestamp'] > split_date]
        
        # Train model
        training_results = self.yield_predictor.train(
            data=train_data,
            feature_cols=feature_cols,
            target_cols=target_cols,
            validation_data=val_data
        )
        
        # Save model
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = f"ml/models/trained/yield_predictor_{timestamp}.h5"
        self.yield_predictor.save_model(model_path)
        
        # Save training results
        results_path = f"ml/results/yield_predictor_results_{timestamp}.json"
        with open(results_path, 'w') as f:
            # Convert numpy types to native Python types for JSON serialization
            serializable_results = self._make_json_serializable(training_results)
            json.dump(serializable_results, f, indent=2)
        
        logger.info("Yield prediction model training completed")
        return training_results
    
    def train_strategy_selector(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Train the strategy selection model"""
        logger.info("Training strategy selection model...")
        
        # Initialize model
        self.strategy_selector = StrategySelector(
            config=self.config["strategy_selector"]
        )
        
        # Train model
        training_results = self.strategy_selector.train(
            data=data,
            episodes=self.config["strategy_selector"]["episodes"]
        )
        
        # Save model
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = f"ml/models/trained/strategy_selector_{timestamp}.h5"
        self.strategy_selector.save_model(model_path)
        
        # Save training results
        results_path = f"ml/results/strategy_selector_results_{timestamp}.json"
        with open(results_path, 'w') as f:
            serializable_results = self._make_json_serializable(training_results)
            json.dump(serializable_results, f, indent=2)
        
        logger.info("Strategy selection model training completed")
        return training_results
    
    def evaluate_models(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Evaluate trained models"""
        logger.info("Evaluating models...")
        
        evaluation_results = {}
        
        # Evaluate yield predictor
        if self.yield_predictor:
            test_data = data.tail(1000)  # Use last 1000 points for testing
            predictions = self.yield_predictor.predict(test_data)
            
            evaluation_results['yield_predictor'] = {
                'predictions_count': len(predictions),
                'feature_importance': self.yield_predictor.get_feature_importance()
            }
        
        # Evaluate strategy selector
        if self.strategy_selector:
            current_state = data.tail(100)  # Use recent data for allocation
            allocation = self.strategy_selector.predict_allocation(current_state)
            
            evaluation_results['strategy_selector'] = {
                'recommended_allocation': allocation
            }
        
        # Save evaluation results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_path = f"ml/results/evaluation_results_{timestamp}.json"
        with open(results_path, 'w') as f:
            serializable_results = self._make_json_serializable(evaluation_results)
            json.dump(serializable_results, f, indent=2)
        
        logger.info("Model evaluation completed")
        return evaluation_results
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert numpy types to JSON serializable types"""
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        else:
            return obj
    
    async def run_full_pipeline(self) -> Dict[str, Any]:
        """Run the complete training pipeline"""
        logger.info("Starting full training pipeline...")
        
        pipeline_results = {}
        
        try:
            # Step 1: Collect data
            raw_data = await self.collect_data()
            pipeline_results['data_collection'] = {
                'status': 'success',
                'data_points': len(raw_data)
            }
            
            # Step 2: Engineer features
            processed_data = self.engineer_features(raw_data)
            pipeline_results['feature_engineering'] = {
                'status': 'success',
                'features_created': len(self.feature_engineer.feature_columns)
            }
            
            # Step 3: Train yield predictor
            yield_results = self.train_yield_predictor(processed_data)
            pipeline_results['yield_predictor'] = {
                'status': 'success',
                'training_results': yield_results
            }
            
            # Step 4: Train strategy selector
            strategy_results = self.train_strategy_selector(processed_data)
            pipeline_results['strategy_selector'] = {
                'status': 'success',
                'training_results': strategy_results
            }
            
            # Step 5: Evaluate models
            evaluation_results = self.evaluate_models(processed_data)
            pipeline_results['evaluation'] = {
                'status': 'success',
                'results': evaluation_results
            }
            
            logger.info("Full training pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            pipeline_results['error'] = str(e)
        
        # Save pipeline results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_path = f"ml/results/pipeline_results_{timestamp}.json"
        with open(results_path, 'w') as f:
            serializable_results = self._make_json_serializable(pipeline_results)
            json.dump(serializable_results, f, indent=2)
        
        return pipeline_results

async def main():
    """Main function for running the training pipeline"""
    parser = argparse.ArgumentParser(description='Train AI models for yield farming optimization')
    parser.add_argument('--config', type=str, default='ml/config/training_config.json',
                       help='Path to training configuration file')
    parser.add_argument('--data-only', action='store_true',
                       help='Only collect data, skip training')
    parser.add_argument('--yield-only', action='store_true',
                       help='Only train yield predictor')
    parser.add_argument('--strategy-only', action='store_true',
                       help='Only train strategy selector')
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = ModelTrainingPipeline(config_path=args.config)
    
    if args.data_only:
        # Only collect data
        data = await pipeline.collect_data()
        print(f"Data collection completed. Collected {len(data)} data points.")
    elif args.yield_only:
        # Only train yield predictor
        data = await pipeline.collect_data()
        processed_data = pipeline.engineer_features(data)
        results = pipeline.train_yield_predictor(processed_data)
        print("Yield predictor training completed.")
    elif args.strategy_only:
        # Only train strategy selector
        data = await pipeline.collect_data()
        processed_data = pipeline.engineer_features(data)
        results = pipeline.train_strategy_selector(processed_data)
        print("Strategy selector training completed.")
    else:
        # Run full pipeline
        results = await pipeline.run_full_pipeline()
        print("Full training pipeline completed.")
        print(f"Results: {results}")

if __name__ == "__main__":
    asyncio.run(main())
