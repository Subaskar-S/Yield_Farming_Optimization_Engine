"""
Strategy selection model using reinforcement learning for DeFi yield farming optimization.
Implements a Deep Q-Network (DQN) for optimal strategy allocation.
"""

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
import random
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class DeFiEnvironment:
    """DeFi yield farming environment for reinforcement learning"""
    
    def __init__(self, 
                 data: pd.DataFrame,
                 initial_balance: float = 100000,
                 transaction_cost: float = 0.003,
                 risk_penalty: float = 0.1):
        
        self.data = data.sort_values(['timestamp']).reset_index(drop=True)
        self.initial_balance = initial_balance
        self.transaction_cost = transaction_cost
        self.risk_penalty = risk_penalty
        
        # Environment state
        self.current_step = 0
        self.balance = initial_balance
        self.portfolio = {}  # {protocol: allocation_percentage}
        self.total_return = 0
        self.max_drawdown = 0
        self.peak_balance = initial_balance
        
        # Available protocols
        self.protocols = list(data['protocol'].unique())
        self.n_protocols = len(self.protocols)
        
        # Action space: allocation percentages for each protocol (0-100%)
        self.action_space_size = self.n_protocols + 1  # +1 for cash position
        
        # State space: market features + portfolio state
        self.state_features = [
            'apy', 'tvl', 'risk_score', 'liquidity_depth',
            'apy_ma_7', 'apy_volatility_7', 'market_share'
        ]
        self.state_size = len(self.state_features) * self.n_protocols + self.n_protocols + 3
        # +n_protocols for current allocations, +3 for balance, return, drawdown
        
    def reset(self) -> np.ndarray:
        """Reset environment to initial state"""
        self.current_step = 0
        self.balance = self.initial_balance
        self.portfolio = {protocol: 0.0 for protocol in self.protocols}
        self.total_return = 0
        self.max_drawdown = 0
        self.peak_balance = self.initial_balance
        
        return self._get_state()
    
    def _get_state(self) -> np.ndarray:
        """Get current state representation"""
        if self.current_step >= len(self.data):
            return np.zeros(self.state_size)
        
        current_data = self.data.iloc[self.current_step]
        state = []
        
        # Market features for each protocol
        for protocol in self.protocols:
            protocol_data = current_data[current_data['protocol'] == protocol]
            
            if len(protocol_data) > 0:
                for feature in self.state_features:
                    state.append(protocol_data[feature].iloc[0] if feature in protocol_data else 0)
            else:
                state.extend([0] * len(self.state_features))
        
        # Current portfolio allocations
        for protocol in self.protocols:
            state.append(self.portfolio.get(protocol, 0))
        
        # Portfolio metrics
        state.extend([
            self.balance / self.initial_balance,  # Normalized balance
            self.total_return,
            self.max_drawdown
        ])
        
        return np.array(state, dtype=np.float32)
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict]:
        """Execute action and return next state, reward, done, info"""
        
        if self.current_step >= len(self.data) - 1:
            return self._get_state(), 0, True, {}
        
        # Normalize action to sum to 1 (portfolio allocation)
        action = np.clip(action, 0, 1)
        action = action / (np.sum(action) + 1e-8)
        
        # Calculate transaction costs
        transaction_cost = 0
        for i, protocol in enumerate(self.protocols):
            old_allocation = self.portfolio.get(protocol, 0)
            new_allocation = action[i]
            transaction_cost += abs(new_allocation - old_allocation) * self.transaction_cost
        
        # Update portfolio
        for i, protocol in enumerate(self.protocols):
            self.portfolio[protocol] = action[i]
        
        # Cash position
        cash_allocation = action[-1] if len(action) > self.n_protocols else 0
        
        # Move to next time step
        self.current_step += 1
        current_data = self.data.iloc[self.current_step]
        
        # Calculate returns
        portfolio_return = 0
        portfolio_risk = 0
        
        for protocol in self.protocols:
            allocation = self.portfolio.get(protocol, 0)
            if allocation > 0:
                protocol_data = current_data[current_data['protocol'] == protocol]
                if len(protocol_data) > 0:
                    apy = protocol_data['apy'].iloc[0] / 100 / 365  # Daily return
                    risk = protocol_data['risk_score'].iloc[0] / 100
                    
                    portfolio_return += allocation * apy
                    portfolio_risk += allocation * risk
        
        # Cash return (assume 0% for simplicity)
        portfolio_return += cash_allocation * 0
        
        # Apply transaction costs
        portfolio_return -= transaction_cost
        
        # Update balance
        self.balance *= (1 + portfolio_return)
        
        # Update metrics
        self.total_return = (self.balance - self.initial_balance) / self.initial_balance
        
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        current_drawdown = (self.peak_balance - self.balance) / self.peak_balance
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        # Calculate reward
        reward = self._calculate_reward(portfolio_return, portfolio_risk, transaction_cost)
        
        # Check if episode is done
        done = self.current_step >= len(self.data) - 1 or self.balance <= 0
        
        info = {
            'balance': self.balance,
            'total_return': self.total_return,
            'max_drawdown': self.max_drawdown,
            'portfolio_return': portfolio_return,
            'portfolio_risk': portfolio_risk,
            'transaction_cost': transaction_cost
        }
        
        return self._get_state(), reward, done, info
    
    def _calculate_reward(self, portfolio_return: float, portfolio_risk: float, transaction_cost: float) -> float:
        """Calculate reward for the current action"""
        
        # Base reward: portfolio return
        reward = portfolio_return
        
        # Risk penalty
        reward -= self.risk_penalty * portfolio_risk
        
        # Transaction cost penalty
        reward -= transaction_cost
        
        # Drawdown penalty
        if self.max_drawdown > 0.1:  # 10% drawdown threshold
            reward -= self.max_drawdown * 2
        
        # Diversification bonus
        active_positions = sum(1 for allocation in self.portfolio.values() if allocation > 0.01)
        if active_positions > 1:
            reward += 0.001  # Small diversification bonus
        
        return reward

class DQNAgent:
    """Deep Q-Network agent for strategy selection"""
    
    def __init__(self,
                 state_size: int,
                 action_size: int,
                 learning_rate: float = 0.001,
                 epsilon: float = 1.0,
                 epsilon_decay: float = 0.995,
                 epsilon_min: float = 0.01,
                 memory_size: int = 10000,
                 batch_size: int = 32):
        
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.batch_size = batch_size
        
        # Experience replay memory
        self.memory = deque(maxlen=memory_size)
        
        # Neural networks
        self.q_network = self._build_model()
        self.target_network = self._build_model()
        self.update_target_network()
        
    def _build_model(self) -> keras.Model:
        """Build the neural network model"""
        
        model = keras.Sequential([
            layers.Dense(256, activation='relu', input_shape=(self.state_size,)),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(128, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(64, activation='relu'),
            layers.Dropout(0.2),
            
            layers.Dense(self.action_size, activation='softmax')  # Softmax for allocation
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss='mse'
        )
        
        return model
    
    def remember(self, state: np.ndarray, action: np.ndarray, reward: float, 
                 next_state: np.ndarray, done: bool):
        """Store experience in replay memory"""
        self.memory.append((state, action, reward, next_state, done))
    
    def act(self, state: np.ndarray) -> np.ndarray:
        """Choose action using epsilon-greedy policy"""
        
        if np.random.random() <= self.epsilon:
            # Random action (exploration)
            action = np.random.dirichlet(np.ones(self.action_size))
        else:
            # Predicted action (exploitation)
            q_values = self.q_network.predict(state.reshape(1, -1), verbose=0)
            action = q_values[0]
        
        return action
    
    def replay(self) -> float:
        """Train the model on a batch of experiences"""
        
        if len(self.memory) < self.batch_size:
            return 0
        
        batch = random.sample(self.memory, self.batch_size)
        states = np.array([e[0] for e in batch])
        actions = np.array([e[1] for e in batch])
        rewards = np.array([e[2] for e in batch])
        next_states = np.array([e[3] for e in batch])
        dones = np.array([e[4] for e in batch])
        
        # Current Q values
        current_q_values = self.q_network.predict(states, verbose=0)
        
        # Next Q values from target network
        next_q_values = self.target_network.predict(next_states, verbose=0)
        
        # Calculate target Q values
        target_q_values = current_q_values.copy()
        
        for i in range(self.batch_size):
            if dones[i]:
                target_q_values[i] = actions[i] * rewards[i]
            else:
                target_q_values[i] = actions[i] * (rewards[i] + 0.95 * np.max(next_q_values[i]))
        
        # Train the model
        history = self.q_network.fit(
            states, target_q_values,
            batch_size=self.batch_size,
            epochs=1,
            verbose=0
        )
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        
        return history.history['loss'][0]
    
    def update_target_network(self):
        """Update target network weights"""
        self.target_network.set_weights(self.q_network.get_weights())
    
    def save_model(self, filepath: str):
        """Save the trained model"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.q_network.save(filepath)
        logger.info(f"DQN model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model"""
        self.q_network = keras.models.load_model(filepath)
        self.target_network = keras.models.load_model(filepath)
        logger.info(f"DQN model loaded from {filepath}")

class StrategySelector:
    """Main strategy selection system"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.agent = None
        self.environment = None
        self.training_history = []
        
    def train(self, 
              data: pd.DataFrame,
              episodes: int = 1000,
              target_update_frequency: int = 100) -> Dict[str, Any]:
        """Train the strategy selection model"""
        
        logger.info("Initializing DeFi environment...")
        self.environment = DeFiEnvironment(data)
        
        logger.info("Initializing DQN agent...")
        self.agent = DQNAgent(
            state_size=self.environment.state_size,
            action_size=self.environment.action_space_size
        )
        
        logger.info(f"Starting training for {episodes} episodes...")
        
        episode_rewards = []
        episode_losses = []
        
        for episode in range(episodes):
            state = self.environment.reset()
            total_reward = 0
            total_loss = 0
            steps = 0
            
            while True:
                action = self.agent.act(state)
                next_state, reward, done, info = self.environment.step(action)
                
                self.agent.remember(state, action, reward, next_state, done)
                
                state = next_state
                total_reward += reward
                steps += 1
                
                # Train the agent
                if len(self.agent.memory) > self.agent.batch_size:
                    loss = self.agent.replay()
                    total_loss += loss
                
                if done:
                    break
            
            # Update target network
            if episode % target_update_frequency == 0:
                self.agent.update_target_network()
            
            episode_rewards.append(total_reward)
            episode_losses.append(total_loss / steps if steps > 0 else 0)
            
            if episode % 100 == 0:
                avg_reward = np.mean(episode_rewards[-100:])
                avg_loss = np.mean(episode_losses[-100:])
                logger.info(f"Episode {episode}, Avg Reward: {avg_reward:.4f}, "
                           f"Avg Loss: {avg_loss:.4f}, Epsilon: {self.agent.epsilon:.4f}")
        
        self.training_history = {
            'episode_rewards': episode_rewards,
            'episode_losses': episode_losses
        }
        
        logger.info("Training completed successfully")
        
        return {
            'final_reward': episode_rewards[-1],
            'avg_reward': np.mean(episode_rewards[-100:]),
            'training_history': self.training_history
        }
    
    def predict_allocation(self, current_state: pd.DataFrame) -> Dict[str, float]:
        """Predict optimal portfolio allocation"""
        
        if self.agent is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Prepare state
        self.environment.current_step = 0
        self.environment.data = current_state
        state = self.environment._get_state()
        
        # Get action (allocation)
        action = self.agent.act(state)
        
        # Convert to allocation dictionary
        allocation = {}
        for i, protocol in enumerate(self.environment.protocols):
            allocation[protocol] = float(action[i])
        
        if len(action) > len(self.environment.protocols):
            allocation['cash'] = float(action[-1])
        
        return allocation
    
    def save_model(self, filepath: str):
        """Save the trained model"""
        if self.agent is None:
            raise ValueError("No model to save")
        
        self.agent.save_model(filepath)
    
    def load_model(self, filepath: str):
        """Load a trained model"""
        # This would need environment setup as well
        # Simplified for now
        pass
