"""
Web3 service for blockchain interactions in the yield farming platform.
Handles smart contract interactions, transaction management, and event monitoring.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_utils import to_checksum_address
import os
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)

@dataclass
class TransactionResult:
    """Transaction execution result"""
    hash: str
    status: bool
    gas_used: int
    block_number: int
    timestamp: datetime
    error: Optional[str] = None

@dataclass
class VaultInfo:
    """Vault information from blockchain"""
    address: str
    name: str
    symbol: str
    asset: str
    total_assets: int
    total_supply: int
    apy: float
    risk_profile: str
    status: str

@dataclass
class StrategyInfo:
    """Strategy information from blockchain"""
    address: str
    name: str
    protocol: str
    asset: str
    total_deposited: int
    apy: float
    risk_score: int
    active: bool

class Web3Service:
    """Web3 service for blockchain interactions"""
    
    def __init__(self, provider_url: str, private_key: Optional[str] = None):
        self.provider_url = provider_url
        self.private_key = private_key
        self.w3 = None
        self.account = None
        
        # Contract addresses (would be loaded from config)
        self.contract_addresses = {
            'vault_factory': os.getenv('VAULT_FACTORY_ADDRESS'),
            'strategy_registry': os.getenv('STRATEGY_REGISTRY_ADDRESS'),
            'automation_registry': os.getenv('AUTOMATION_REGISTRY_ADDRESS')
        }
        
        # Contract instances
        self.contracts = {}
        
        # Event filters
        self.event_filters = {}
        
        # Transaction management
        self.pending_transactions = {}
        self.transaction_history = []
        
        # Metrics
        self.metrics = {
            'total_transactions': 0,
            'successful_transactions': 0,
            'failed_transactions': 0,
            'total_gas_used': 0,
            'average_gas_price': 0
        }
    
    async def initialize(self):
        """Initialize Web3 connection and contracts"""
        try:
            # Initialize Web3
            self.w3 = Web3(Web3.HTTPProvider(self.provider_url))
            
            # Add PoA middleware if needed
            if self.w3.eth.chain_id in [137, 80001]:  # Polygon networks
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            # Check connection
            if not self.w3.is_connected():
                raise Exception("Failed to connect to Web3 provider")
            
            # Initialize account if private key provided
            if self.private_key:
                self.account = Account.from_key(self.private_key)
                logger.info(f"Initialized account: {self.account.address}")
            
            # Load contract ABIs and initialize contracts
            await self._load_contracts()
            
            # Start event monitoring
            asyncio.create_task(self._monitor_events())
            
            logger.info(f"Web3 service initialized on chain {self.w3.eth.chain_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Web3 service: {str(e)}")
            raise
    
    async def _load_contracts(self):
        """Load smart contracts"""
        
        # Load ABIs
        contract_abis = {
            'vault_factory': self._load_abi('VaultFactory.json'),
            'yield_vault': self._load_abi('YieldVault.json'),
            'base_strategy': self._load_abi('BaseStrategy.json'),
            'strategy_registry': self._load_abi('StrategyRegistry.json')
        }
        
        # Initialize contract instances
        for contract_name, address in self.contract_addresses.items():
            if address and contract_name in contract_abis:
                try:
                    self.contracts[contract_name] = self.w3.eth.contract(
                        address=to_checksum_address(address),
                        abi=contract_abis[contract_name]
                    )
                    logger.info(f"Loaded contract {contract_name} at {address}")
                except Exception as e:
                    logger.error(f"Failed to load contract {contract_name}: {str(e)}")
    
    def _load_abi(self, filename: str) -> List[Dict]:
        """Load contract ABI from file"""
        abi_path = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'contracts')
        
        # Try to load from artifacts
        try:
            with open(os.path.join(abi_path, filename), 'r') as f:
                artifact = json.load(f)
                return artifact.get('abi', [])
        except FileNotFoundError:
            logger.warning(f"ABI file {filename} not found, using minimal ABI")
            return self._get_minimal_abi(filename)
    
    def _get_minimal_abi(self, filename: str) -> List[Dict]:
        """Get minimal ABI for basic functionality"""
        # Return basic ERC20/ERC4626 ABI for now
        return [
            {
                "inputs": [],
                "name": "totalAssets",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
    
    async def is_connected(self) -> bool:
        """Check if Web3 is connected"""
        try:
            return self.w3 and self.w3.is_connected()
        except:
            return False
    
    async def get_block_number(self) -> int:
        """Get current block number"""
        return self.w3.eth.block_number
    
    async def get_gas_price(self) -> int:
        """Get current gas price"""
        return self.w3.eth.gas_price
    
    async def get_balance(self, address: str) -> int:
        """Get ETH balance of address"""
        return self.w3.eth.get_balance(to_checksum_address(address))
    
    async def send_transaction(self, 
                             contract_function,
                             gas_limit: Optional[int] = None,
                             gas_price: Optional[int] = None) -> TransactionResult:
        """Send a transaction to the blockchain"""
        
        if not self.account:
            raise ValueError("No account configured for transactions")
        
        try:
            # Build transaction
            transaction = contract_function.build_transaction({
                'from': self.account.address,
                'gas': gas_limit or 500000,
                'gasPrice': gas_price or await self.get_gas_price(),
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Create result
            result = TransactionResult(
                hash=tx_hash.hex(),
                status=receipt.status == 1,
                gas_used=receipt.gasUsed,
                block_number=receipt.blockNumber,
                timestamp=datetime.now()
            )
            
            # Update metrics
            self.metrics['total_transactions'] += 1
            if result.status:
                self.metrics['successful_transactions'] += 1
            else:
                self.metrics['failed_transactions'] += 1
            self.metrics['total_gas_used'] += result.gas_used
            
            # Store in history
            self.transaction_history.append(result)
            
            logger.info(f"Transaction {result.hash} completed with status {result.status}")
            return result
            
        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}")
            self.metrics['failed_transactions'] += 1
            raise
    
    async def call_contract_function(self, 
                                   contract_name: str,
                                   function_name: str,
                                   *args) -> Any:
        """Call a read-only contract function"""
        
        if contract_name not in self.contracts:
            raise ValueError(f"Contract {contract_name} not loaded")
        
        contract = self.contracts[contract_name]
        
        try:
            function = getattr(contract.functions, function_name)
            return function(*args).call()
        except Exception as e:
            logger.error(f"Contract call failed: {str(e)}")
            raise
    
    async def get_vault_info(self, vault_address: str) -> VaultInfo:
        """Get vault information from blockchain"""
        
        try:
            vault_contract = self.w3.eth.contract(
                address=to_checksum_address(vault_address),
                abi=self._load_abi('YieldVault.json')
            )
            
            # Get vault data
            vault_info_data = vault_contract.functions.getVaultInfo().call()
            
            return VaultInfo(
                address=vault_address,
                name=vault_info_data[0],
                symbol=vault_info_data[1],
                asset=vault_info_data[2],
                total_assets=vault_info_data[5],
                total_supply=vault_info_data[6],
                apy=0,  # Would calculate from historical data
                risk_profile=str(vault_info_data[3]),
                status=str(vault_info_data[4])
            )
            
        except Exception as e:
            logger.error(f"Failed to get vault info: {str(e)}")
            raise
    
    async def get_strategy_info(self, strategy_address: str) -> StrategyInfo:
        """Get strategy information from blockchain"""
        
        try:
            strategy_contract = self.w3.eth.contract(
                address=to_checksum_address(strategy_address),
                abi=self._load_abi('BaseStrategy.json')
            )
            
            # Get strategy data
            strategy_info_data = strategy_contract.functions.getStrategyInfo().call()
            
            return StrategyInfo(
                address=strategy_address,
                name=strategy_info_data[0],
                protocol=strategy_info_data[1],
                asset=strategy_info_data[2],
                total_deposited=strategy_info_data[4],
                apy=strategy_info_data[7] / 100,  # Convert from basis points
                risk_score=strategy_info_data[6],
                active=strategy_info_data[3] == 0  # Assuming 0 = ACTIVE
            )
            
        except Exception as e:
            logger.error(f"Failed to get strategy info: {str(e)}")
            raise
    
    async def deploy_vault(self, 
                         asset_address: str,
                         name: str,
                         symbol: str,
                         risk_profile: int) -> str:
        """Deploy a new yield vault"""
        
        if 'vault_factory' not in self.contracts:
            raise ValueError("Vault factory contract not loaded")
        
        try:
            factory = self.contracts['vault_factory']
            
            # Deploy vault
            deploy_function = factory.functions.deployVault(
                asset_address,
                name,
                symbol,
                risk_profile,
                self.account.address  # admin
            )
            
            result = await self.send_transaction(deploy_function)
            
            if result.status:
                # Extract vault address from logs
                vault_address = self._extract_vault_address_from_logs(result.hash)
                logger.info(f"Vault deployed at {vault_address}")
                return vault_address
            else:
                raise Exception("Vault deployment failed")
                
        except Exception as e:
            logger.error(f"Failed to deploy vault: {str(e)}")
            raise
    
    def _extract_vault_address_from_logs(self, tx_hash: str) -> str:
        """Extract vault address from transaction logs"""
        # This would parse the transaction receipt logs
        # For now, return placeholder
        return "0x..."
    
    async def _monitor_events(self):
        """Monitor blockchain events"""
        logger.info("Starting event monitoring...")
        
        while True:
            try:
                # Monitor vault events
                await self._process_vault_events()
                
                # Monitor strategy events
                await self._process_strategy_events()
                
                # Wait before next check
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in event monitoring: {str(e)}")
                await asyncio.sleep(10)
    
    async def _process_vault_events(self):
        """Process vault-related events"""
        # Implementation would filter and process vault events
        pass
    
    async def _process_strategy_events(self):
        """Process strategy-related events"""
        # Implementation would filter and process strategy events
        pass
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get Web3 service metrics"""
        
        current_block = await self.get_block_number()
        gas_price = await self.get_gas_price()
        
        return {
            'connection_status': await self.is_connected(),
            'current_block': current_block,
            'gas_price': gas_price,
            'chain_id': self.w3.eth.chain_id,
            'account_address': self.account.address if self.account else None,
            'account_balance': await self.get_balance(self.account.address) if self.account else 0,
            'transactions': self.metrics,
            'contracts_loaded': len(self.contracts),
            'recent_transactions': len([
                tx for tx in self.transaction_history 
                if tx.timestamp > datetime.now() - timedelta(hours=1)
            ])
        }
    
    async def cleanup(self):
        """Cleanup Web3 service"""
        logger.info("Cleaning up Web3 service...")
        
        # Cancel event monitoring tasks
        # Close connections
        # Save transaction history
        pass
