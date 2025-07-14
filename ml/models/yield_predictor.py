"""
Yield prediction model using TensorFlow for DeFi yield farming optimization.
Implements LSTM-based time series prediction for APY forecasting.
"""

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class YieldPredictor:
    """LSTM-based yield prediction model"""
    
    def __init__(self, 
                 sequence_length: int = 30,
                 prediction_horizon: int = 7,
                 model_config: Dict = None):
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.model = None
        self.history = None
        self.feature_columns = []
        self.target_columns = []
        
        # Default model configuration
        self.config = {
            'lstm_units': [128, 64, 32],
            'dropout_rate': 0.2,
            'learning_rate': 0.001,
            'batch_size': 32,
            'epochs': 100,
            'validation_split': 0.2,
            'early_stopping_patience': 10,
            'reduce_lr_patience': 5
        }
        
        if model_config:
            self.config.update(model_config)
    
    def prepare_sequences(self, 
                         data: pd.DataFrame, 
                         feature_cols: List[str], 
                         target_cols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare sequences for LSTM training"""
        
        # Sort data by protocol and timestamp
        data = data.sort_values(['protocol', 'timestamp'])
        
        X_sequences = []
        y_sequences = []
        
        # Create sequences for each protocol
        for protocol in data['protocol'].unique():
            protocol_data = data[data['protocol'] == protocol].copy()
            
            if len(protocol_data) < self.sequence_length + self.prediction_horizon:
                continue
            
            # Extract features and targets
            features = protocol_data[feature_cols].values
            targets = protocol_data[target_cols].values
            
            # Create sequences
            for i in range(len(features) - self.sequence_length - self.prediction_horizon + 1):
                X_sequences.append(features[i:i + self.sequence_length])
                y_sequences.append(targets[i + self.sequence_length:i + self.sequence_length + self.prediction_horizon])
        
        return np.array(X_sequences), np.array(y_sequences)
    
    def build_model(self, input_shape: Tuple, output_shape: Tuple) -> keras.Model:
        """Build LSTM model architecture"""
        
        model = keras.Sequential()
        
        # Input layer
        model.add(layers.Input(shape=input_shape))
        
        # LSTM layers
        for i, units in enumerate(self.config['lstm_units']):
            return_sequences = i < len(self.config['lstm_units']) - 1
            
            model.add(layers.LSTM(
                units=units,
                return_sequences=return_sequences,
                dropout=self.config['dropout_rate'],
                recurrent_dropout=self.config['dropout_rate']
            ))
            
            if return_sequences:
                model.add(layers.BatchNormalization())
        
        # Dense layers for multi-step prediction
        model.add(layers.Dense(128, activation='relu'))
        model.add(layers.Dropout(self.config['dropout_rate']))
        model.add(layers.Dense(64, activation='relu'))
        model.add(layers.Dropout(self.config['dropout_rate']))
        
        # Output layer
        model.add(layers.Dense(
            output_shape[0] * output_shape[1],
            activation='linear'
        ))
        model.add(layers.Reshape(output_shape))
        
        # Compile model
        optimizer = keras.optimizers.Adam(learning_rate=self.config['learning_rate'])
        model.compile(
            optimizer=optimizer,
            loss='mse',
            metrics=['mae', 'mape']
        )
        
        return model
    
    def train(self, 
              data: pd.DataFrame, 
              feature_cols: List[str], 
              target_cols: List[str],
              validation_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Train the yield prediction model"""
        
        logger.info("Preparing training data...")
        
        # Store column names
        self.feature_columns = feature_cols
        self.target_columns = target_cols
        
        # Prepare sequences
        X, y = self.prepare_sequences(data, feature_cols, target_cols)
        
        if len(X) == 0:
            raise ValueError("No sequences could be created from the data")
        
        logger.info(f"Created {len(X)} sequences for training")
        logger.info(f"Input shape: {X.shape}, Output shape: {y.shape}")
        
        # Split data
        if validation_data is None:
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=self.config['validation_split'], random_state=42
            )
        else:
            X_train, y_train = X, y
            X_val, y_val = self.prepare_sequences(validation_data, feature_cols, target_cols)
        
        # Build model
        input_shape = (X_train.shape[1], X_train.shape[2])
        output_shape = (y_train.shape[1], y_train.shape[2])
        
        self.model = self.build_model(input_shape, output_shape)
        
        logger.info("Model architecture:")
        self.model.summary()
        
        # Callbacks
        callbacks = [
            keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=self.config['early_stopping_patience'],
                restore_best_weights=True
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=self.config['reduce_lr_patience'],
                min_lr=1e-7
            ),
            keras.callbacks.ModelCheckpoint(
                'ml/models/checkpoints/yield_predictor_best.h5',
                monitor='val_loss',
                save_best_only=True
            )
        ]
        
        # Create checkpoint directory
        os.makedirs('ml/models/checkpoints', exist_ok=True)
        
        # Train model
        logger.info("Starting model training...")
        
        self.history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            batch_size=self.config['batch_size'],
            epochs=self.config['epochs'],
            callbacks=callbacks,
            verbose=1
        )
        
        # Evaluate model
        train_loss = self.model.evaluate(X_train, y_train, verbose=0)
        val_loss = self.model.evaluate(X_val, y_val, verbose=0)
        
        # Calculate additional metrics
        y_train_pred = self.model.predict(X_train)
        y_val_pred = self.model.predict(X_val)
        
        train_metrics = self._calculate_metrics(y_train, y_train_pred)
        val_metrics = self._calculate_metrics(y_val, y_val_pred)
        
        training_results = {
            'train_loss': train_loss,
            'val_loss': val_loss,
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'history': self.history.history,
            'model_config': self.config
        }
        
        logger.info("Training completed successfully")
        logger.info(f"Final validation loss: {val_loss[0]:.6f}")
        
        return training_results
    
    def predict(self, 
                data: pd.DataFrame, 
                protocol: str = None) -> pd.DataFrame:
        """Make predictions using the trained model"""
        
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Filter by protocol if specified
        if protocol:
            data = data[data['protocol'] == protocol].copy()
        
        # Prepare sequences
        X, _ = self.prepare_sequences(data, self.feature_columns, self.target_columns)
        
        if len(X) == 0:
            logger.warning("No sequences could be created for prediction")
            return pd.DataFrame()
        
        # Make predictions
        predictions = self.model.predict(X)
        
        # Convert predictions to DataFrame
        results = []
        sequence_idx = 0
        
        for protocol in data['protocol'].unique():
            protocol_data = data[data['protocol'] == protocol].copy()
            
            if len(protocol_data) < self.sequence_length + self.prediction_horizon:
                continue
            
            for i in range(len(protocol_data) - self.sequence_length - self.prediction_horizon + 1):
                base_timestamp = protocol_data.iloc[i + self.sequence_length]['timestamp']
                
                for horizon in range(self.prediction_horizon):
                    for target_idx, target_col in enumerate(self.target_columns):
                        results.append({
                            'protocol': protocol,
                            'timestamp': base_timestamp,
                            'prediction_horizon': horizon + 1,
                            'target': target_col,
                            'predicted_value': predictions[sequence_idx, horizon, target_idx],
                            'sequence_idx': sequence_idx
                        })
                
                sequence_idx += 1
        
        return pd.DataFrame(results)
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate evaluation metrics"""
        
        # Flatten arrays for metric calculation
        y_true_flat = y_true.reshape(-1, y_true.shape[-1])
        y_pred_flat = y_pred.reshape(-1, y_pred.shape[-1])
        
        metrics = {}
        
        for i, target_col in enumerate(self.target_columns):
            y_true_col = y_true_flat[:, i]
            y_pred_col = y_pred_flat[:, i]
            
            # Remove NaN values
            mask = ~(np.isnan(y_true_col) | np.isnan(y_pred_col))
            y_true_col = y_true_col[mask]
            y_pred_col = y_pred_col[mask]
            
            if len(y_true_col) > 0:
                metrics[f'{target_col}_mse'] = mean_squared_error(y_true_col, y_pred_col)
                metrics[f'{target_col}_mae'] = mean_absolute_error(y_true_col, y_pred_col)
                metrics[f'{target_col}_r2'] = r2_score(y_true_col, y_pred_col)
                
                # MAPE (Mean Absolute Percentage Error)
                mape = np.mean(np.abs((y_true_col - y_pred_col) / (y_true_col + 1e-8))) * 100
                metrics[f'{target_col}_mape'] = mape
        
        return metrics
    
    def save_model(self, filepath: str):
        """Save the trained model"""
        if self.model is None:
            raise ValueError("No model to save")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save model
        self.model.save(filepath)
        
        # Save metadata
        metadata = {
            'sequence_length': self.sequence_length,
            'prediction_horizon': self.prediction_horizon,
            'feature_columns': self.feature_columns,
            'target_columns': self.target_columns,
            'config': self.config
        }
        
        metadata_path = filepath.replace('.h5', '_metadata.joblib')
        joblib.dump(metadata, metadata_path)
        
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model"""
        
        # Load model
        self.model = keras.models.load_model(filepath)
        
        # Load metadata
        metadata_path = filepath.replace('.h5', '_metadata.joblib')
        if os.path.exists(metadata_path):
            metadata = joblib.load(metadata_path)
            self.sequence_length = metadata['sequence_length']
            self.prediction_horizon = metadata['prediction_horizon']
            self.feature_columns = metadata['feature_columns']
            self.target_columns = metadata['target_columns']
            self.config = metadata['config']
        
        logger.info(f"Model loaded from {filepath}")
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance using permutation importance"""
        # This is a simplified version - in practice, you'd implement
        # proper permutation importance for time series
        
        if self.model is None:
            raise ValueError("Model not trained")
        
        # Placeholder implementation
        importance = {}
        for i, feature in enumerate(self.feature_columns):
            # Random importance for demonstration
            importance[feature] = np.random.random()
        
        return importance
    
    def plot_training_history(self):
        """Plot training history"""
        if self.history is None:
            raise ValueError("No training history available")
        
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Loss
        axes[0, 0].plot(self.history.history['loss'], label='Training Loss')
        axes[0, 0].plot(self.history.history['val_loss'], label='Validation Loss')
        axes[0, 0].set_title('Model Loss')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].set_ylabel('Loss')
        axes[0, 0].legend()
        
        # MAE
        axes[0, 1].plot(self.history.history['mae'], label='Training MAE')
        axes[0, 1].plot(self.history.history['val_mae'], label='Validation MAE')
        axes[0, 1].set_title('Mean Absolute Error')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].set_ylabel('MAE')
        axes[0, 1].legend()
        
        # MAPE
        axes[1, 0].plot(self.history.history['mape'], label='Training MAPE')
        axes[1, 0].plot(self.history.history['val_mape'], label='Validation MAPE')
        axes[1, 0].set_title('Mean Absolute Percentage Error')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('MAPE')
        axes[1, 0].legend()
        
        # Learning rate (if available)
        if 'lr' in self.history.history:
            axes[1, 1].plot(self.history.history['lr'])
            axes[1, 1].set_title('Learning Rate')
            axes[1, 1].set_xlabel('Epoch')
            axes[1, 1].set_ylabel('Learning Rate')
            axes[1, 1].set_yscale('log')
        
        plt.tight_layout()
        plt.savefig('ml/models/training_history.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        return fig
