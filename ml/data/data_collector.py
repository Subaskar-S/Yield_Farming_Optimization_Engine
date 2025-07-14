"""
Data collection module for DeFi yield farming optimization.
Collects historical data from various DeFi protocols and market sources.
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import json
import os
from web3 import Web3
import ccxt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProtocolData:
    """Data structure for protocol information"""
    name: str
    address: str
    apy: float
    tvl: float
    volume_24h: float
    timestamp: datetime
    risk_score: float
    liquidity_depth: float

@dataclass
class MarketData:
    """Data structure for market information"""
    symbol: str
    price: float
    volume_24h: float
    market_cap: float
    volatility: float
    timestamp: datetime

class DeFiDataCollector:
    """Main data collector for DeFi protocols and market data"""
    
    def __init__(self, config_path: str = "config/data_sources.json"):
        self.config = self._load_config(config_path)
        self.session = None
        self.web3 = None
        self._initialize_web3()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration for data sources"""
        default_config = {
            "apis": {
                "coingecko": "https://api.coingecko.com/api/v3",
                "defipulse": "https://data-api.defipulse.com/api/v1",
                "dune": "https://api.dune.com/api/v1",
                "compound": "https://api.compound.finance/api/v2",
                "aave": "https://aave-api-v2.aave.com",
                "yearn": "https://api.yearn.finance/v1"
            },
            "protocols": {
                "compound": {
                    "name": "Compound",
                    "comptroller": "0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B",
                    "tokens": ["USDC", "USDT", "DAI", "ETH", "WBTC"]
                },
                "aave": {
                    "name": "Aave",
                    "lending_pool": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
                    "tokens": ["USDC", "USDT", "DAI", "ETH", "WBTC"]
                },
                "yearn": {
                    "name": "Yearn Finance",
                    "registry": "0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804",
                    "tokens": ["USDC", "USDT", "DAI", "ETH", "WBTC"]
                }
            },
            "update_intervals": {
                "market_data": 300,  # 5 minutes
                "protocol_data": 3600,  # 1 hour
                "historical_data": 86400  # 24 hours
            }
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return default_config
    
    def _initialize_web3(self):
        """Initialize Web3 connection"""
        infura_url = os.getenv('INFURA_API_KEY')
        if infura_url:
            self.web3 = Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{infura_url}"))
        else:
            logger.warning("No Infura API key found, Web3 functionality limited")
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def collect_market_data(self, symbols: List[str]) -> List[MarketData]:
        """Collect current market data for given symbols"""
        market_data = []
        
        try:
            # CoinGecko API for market data
            url = f"{self.config['apis']['coingecko']}/simple/price"
            params = {
                'ids': ','.join(symbols),
                'vs_currencies': 'usd',
                'include_market_cap': 'true',
                'include_24hr_vol': 'true',
                'include_24hr_change': 'true'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for symbol, info in data.items():
                        market_data.append(MarketData(
                            symbol=symbol,
                            price=info.get('usd', 0),
                            volume_24h=info.get('usd_24h_vol', 0),
                            market_cap=info.get('usd_market_cap', 0),
                            volatility=abs(info.get('usd_24h_change', 0)),
                            timestamp=datetime.now()
                        ))
                else:
                    logger.error(f"Failed to fetch market data: {response.status}")
        
        except Exception as e:
            logger.error(f"Error collecting market data: {e}")
        
        return market_data
    
    async def collect_compound_data(self) -> List[ProtocolData]:
        """Collect data from Compound protocol"""
        protocol_data = []
        
        try:
            url = f"{self.config['apis']['compound']}/ctoken"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for token_data in data.get('cToken', []):
                        if token_data.get('underlying_symbol') in self.config['protocols']['compound']['tokens']:
                            protocol_data.append(ProtocolData(
                                name=f"Compound {token_data.get('underlying_symbol')}",
                                address=token_data.get('token_address'),
                                apy=float(token_data.get('supply_rate', {}).get('value', 0)) * 100,
                                tvl=float(token_data.get('total_supply', {}).get('value', 0)),
                                volume_24h=0,  # Not available in this API
                                timestamp=datetime.now(),
                                risk_score=self._calculate_compound_risk_score(token_data),
                                liquidity_depth=float(token_data.get('cash', {}).get('value', 0))
                            ))
                else:
                    logger.error(f"Failed to fetch Compound data: {response.status}")
        
        except Exception as e:
            logger.error(f"Error collecting Compound data: {e}")
        
        return protocol_data
    
    async def collect_aave_data(self) -> List[ProtocolData]:
        """Collect data from Aave protocol"""
        protocol_data = []
        
        try:
            url = f"{self.config['apis']['aave']}/data/reserves-overview"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for reserve in data:
                        if reserve.get('symbol') in self.config['protocols']['aave']['tokens']:
                            protocol_data.append(ProtocolData(
                                name=f"Aave {reserve.get('symbol')}",
                                address=reserve.get('id'),
                                apy=float(reserve.get('liquidityRate', 0)) / 1e25 * 100,  # Convert from ray
                                tvl=float(reserve.get('totalLiquidity', 0)),
                                volume_24h=0,  # Calculate from historical data if needed
                                timestamp=datetime.now(),
                                risk_score=self._calculate_aave_risk_score(reserve),
                                liquidity_depth=float(reserve.get('availableLiquidity', 0))
                            ))
                else:
                    logger.error(f"Failed to fetch Aave data: {response.status}")
        
        except Exception as e:
            logger.error(f"Error collecting Aave data: {e}")
        
        return protocol_data
    
    async def collect_yearn_data(self) -> List[ProtocolData]:
        """Collect data from Yearn Finance"""
        protocol_data = []
        
        try:
            url = f"{self.config['apis']['yearn']}/vaults/all"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for vault in data:
                        if vault.get('token', {}).get('symbol') in self.config['protocols']['yearn']['tokens']:
                            protocol_data.append(ProtocolData(
                                name=f"Yearn {vault.get('token', {}).get('symbol')}",
                                address=vault.get('address'),
                                apy=float(vault.get('apy', {}).get('net_apy', 0)) * 100,
                                tvl=float(vault.get('tvl', {}).get('value', 0)),
                                volume_24h=0,  # Not directly available
                                timestamp=datetime.now(),
                                risk_score=self._calculate_yearn_risk_score(vault),
                                liquidity_depth=float(vault.get('tvl', {}).get('value', 0))
                            ))
                else:
                    logger.error(f"Failed to fetch Yearn data: {response.status}")
        
        except Exception as e:
            logger.error(f"Error collecting Yearn data: {e}")
        
        return protocol_data
    
    def _calculate_compound_risk_score(self, token_data: Dict) -> float:
        """Calculate risk score for Compound protocol"""
        # Factors: utilization rate, collateral factor, liquidation threshold
        utilization_rate = float(token_data.get('utilization', {}).get('value', 0))
        collateral_factor = float(token_data.get('collateral_factor', {}).get('value', 0))
        
        # Higher utilization and collateral factor = higher risk
        risk_score = (utilization_rate * 0.6 + collateral_factor * 0.4) * 100
        return min(risk_score, 100)
    
    def _calculate_aave_risk_score(self, reserve: Dict) -> float:
        """Calculate risk score for Aave protocol"""
        utilization_rate = float(reserve.get('utilizationRate', 0)) / 1e25
        liquidation_threshold = float(reserve.get('liquidationThreshold', 0)) / 10000
        
        risk_score = (utilization_rate * 0.7 + liquidation_threshold * 0.3) * 100
        return min(risk_score, 100)
    
    def _calculate_yearn_risk_score(self, vault: Dict) -> float:
        """Calculate risk score for Yearn vault"""
        # Use strategy risk and historical volatility
        strategies = vault.get('strategies', [])
        avg_risk = sum(float(s.get('risk', 50)) for s in strategies) / len(strategies) if strategies else 50
        
        return min(avg_risk, 100)
    
    async def collect_historical_data(self, days: int = 30) -> pd.DataFrame:
        """Collect historical data for analysis"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Collect data from all protocols
        all_data = []
        
        # Market data
        market_symbols = ['ethereum', 'bitcoin', 'usd-coin', 'tether', 'dai']
        market_data = await self.collect_market_data(market_symbols)
        
        # Protocol data
        compound_data = await self.collect_compound_data()
        aave_data = await self.collect_aave_data()
        yearn_data = await self.collect_yearn_data()
        
        # Combine all data
        all_protocol_data = compound_data + aave_data + yearn_data
        
        # Convert to DataFrame
        df_data = []
        for protocol in all_protocol_data:
            df_data.append({
                'timestamp': protocol.timestamp,
                'protocol': protocol.name,
                'address': protocol.address,
                'apy': protocol.apy,
                'tvl': protocol.tvl,
                'volume_24h': protocol.volume_24h,
                'risk_score': protocol.risk_score,
                'liquidity_depth': protocol.liquidity_depth
            })
        
        return pd.DataFrame(df_data)
    
    async def save_data(self, data: pd.DataFrame, filename: str):
        """Save collected data to file"""
        os.makedirs('ml/data/raw', exist_ok=True)
        filepath = f'ml/data/raw/{filename}'
        data.to_csv(filepath, index=False)
        logger.info(f"Data saved to {filepath}")

# Example usage
async def main():
    """Example usage of the data collector"""
    async with DeFiDataCollector() as collector:
        # Collect current data
        historical_data = await collector.collect_historical_data(days=7)
        await collector.save_data(historical_data, 'defi_data_sample.csv')
        
        print(f"Collected {len(historical_data)} data points")
        print(historical_data.head())

if __name__ == "__main__":
    asyncio.run(main())
