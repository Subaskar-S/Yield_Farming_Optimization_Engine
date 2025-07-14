"""
Chainlink Keepers integration for automated DeFi yield farming operations.
Manages upkeep registration, monitoring, and execution.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from web3 import Web3
from web3.contract import Contract
from eth_account import Account
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class KeeperJob:
    """Represents a keeper job configuration"""
    name: str
    contract_address: str
    function_name: str
    check_data: bytes
    gas_limit: int
    trigger_condition: str
    frequency: int  # seconds
    last_execution: Optional[datetime] = None
    active: bool = True

@dataclass
class UpkeepInfo:
    """Chainlink upkeep information"""
    upkeep_id: int
    target: str
    execute_gas: int
    check_data: bytes
    balance: int
    admin: str
    max_valid_block_number: int
    last_perform_block_number: int
    amount_spent: int
    paused: bool

class ChainlinkKeeperManager:
    """Manages Chainlink Keepers for automated DeFi operations"""
    
    def __init__(self, 
                 web3_provider: str,
                 private_key: str,
                 keeper_registry_address: str,
                 link_token_address: str):
        
        self.w3 = Web3(Web3.HTTPProvider(web3_provider))
        self.account = Account.from_key(private_key)
        self.keeper_registry_address = keeper_registry_address
        self.link_token_address = link_token_address
        
        # Load contract ABIs
        self.keeper_registry_abi = self._load_abi('chainlink_keeper_registry.json')
        self.link_token_abi = self._load_abi('link_token.json')
        
        # Initialize contracts
        self.keeper_registry = self.w3.eth.contract(
            address=keeper_registry_address,
            abi=self.keeper_registry_abi
        )
        self.link_token = self.w3.eth.contract(
            address=link_token_address,
            abi=self.link_token_abi
        )
        
        # Job management
        self.jobs: Dict[str, KeeperJob] = {}
        self.upkeeps: Dict[int, UpkeepInfo] = {}
        
        logger.info(f"Initialized Chainlink Keeper Manager for account: {self.account.address}")
    
    def _load_abi(self, filename: str) -> List[Dict]:
        """Load contract ABI from file"""
        abi_path = os.path.join(os.path.dirname(__file__), 'abis', filename)
        
        # Default ABI if file doesn't exist
        if not os.path.exists(abi_path):
            logger.warning(f"ABI file {filename} not found, using minimal ABI")
            return self._get_minimal_abi(filename)
        
        with open(abi_path, 'r') as f:
            return json.load(f)
    
    def _get_minimal_abi(self, filename: str) -> List[Dict]:
        """Get minimal ABI for basic functionality"""
        if 'keeper_registry' in filename:
            return [
                {
                    "inputs": [
                        {"name": "name", "type": "string"},
                        {"name": "encryptedEmail", "type": "bytes"},
                        {"name": "upkeepContract", "type": "address"},
                        {"name": "gasLimit", "type": "uint32"},
                        {"name": "adminAddress", "type": "address"},
                        {"name": "checkData", "type": "bytes"},
                        {"name": "amount", "type": "uint96"},
                        {"name": "source", "type": "uint8"}
                    ],
                    "name": "registerUpkeep",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "inputs": [{"name": "id", "type": "uint256"}],
                    "name": "getUpkeep",
                    "outputs": [
                        {"name": "target", "type": "address"},
                        {"name": "executeGas", "type": "uint32"},
                        {"name": "checkData", "type": "bytes"},
                        {"name": "balance", "type": "uint96"},
                        {"name": "lastKeeper", "type": "address"},
                        {"name": "admin", "type": "address"},
                        {"name": "maxValidBlocknumber", "type": "uint64"},
                        {"name": "amountSpent", "type": "uint96"}
                    ],
                    "type": "function"
                }
            ]
        elif 'link_token' in filename:
            return [
                {
                    "inputs": [
                        {"name": "to", "type": "address"},
                        {"name": "value", "type": "uint256"}
                    ],
                    "name": "transfer",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function"
                },
                {
                    "inputs": [{"name": "owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                }
            ]
        return []
    
    async def register_upkeep(self,
                            name: str,
                            target_contract: str,
                            gas_limit: int,
                            check_data: bytes = b'',
                            funding_amount: int = 5 * 10**18) -> int:  # 5 LINK default
        """Register a new upkeep with Chainlink Keepers"""
        
        try:
            logger.info(f"Registering upkeep: {name}")
            
            # Check LINK balance
            link_balance = self.link_token.functions.balanceOf(self.account.address).call()
            if link_balance < funding_amount:
                raise ValueError(f"Insufficient LINK balance. Need {funding_amount}, have {link_balance}")
            
            # Approve LINK spending
            approve_tx = self.link_token.functions.approve(
                self.keeper_registry_address,
                funding_amount
            ).build_transaction({
                'from': self.account.address,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            signed_approve = self.account.sign_transaction(approve_tx)
            approve_hash = self.w3.eth.send_raw_transaction(signed_approve.rawTransaction)
            
            # Wait for approval confirmation
            self.w3.eth.wait_for_transaction_receipt(approve_hash)
            logger.info("LINK approval confirmed")
            
            # Register upkeep
            register_tx = self.keeper_registry.functions.registerUpkeep(
                name,
                b'',  # encrypted email
                target_contract,
                gas_limit,
                self.account.address,  # admin
                check_data,
                funding_amount,
                0  # source
            ).build_transaction({
                'from': self.account.address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            signed_register = self.account.sign_transaction(register_tx)
            register_hash = self.w3.eth.send_raw_transaction(signed_register.rawTransaction)
            
            # Wait for registration confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(register_hash)
            
            # Extract upkeep ID from logs
            upkeep_id = self._extract_upkeep_id_from_receipt(receipt)
            
            logger.info(f"Upkeep registered successfully. ID: {upkeep_id}")
            return upkeep_id
            
        except Exception as e:
            logger.error(f"Failed to register upkeep: {str(e)}")
            raise
    
    def _extract_upkeep_id_from_receipt(self, receipt) -> int:
        """Extract upkeep ID from transaction receipt"""
        # This would parse the logs to find the UpkeepRegistered event
        # For now, return a placeholder
        return 1  # Placeholder
    
    async def get_upkeep_info(self, upkeep_id: int) -> UpkeepInfo:
        """Get information about an upkeep"""
        
        try:
            upkeep_data = self.keeper_registry.functions.getUpkeep(upkeep_id).call()
            
            return UpkeepInfo(
                upkeep_id=upkeep_id,
                target=upkeep_data[0],
                execute_gas=upkeep_data[1],
                check_data=upkeep_data[2],
                balance=upkeep_data[3],
                admin=upkeep_data[5],
                max_valid_block_number=upkeep_data[6],
                last_perform_block_number=0,  # Would need additional call
                amount_spent=upkeep_data[7],
                paused=False  # Would need additional call
            )
            
        except Exception as e:
            logger.error(f"Failed to get upkeep info: {str(e)}")
            raise
    
    def add_job(self, job: KeeperJob):
        """Add a keeper job to management"""
        self.jobs[job.name] = job
        logger.info(f"Added keeper job: {job.name}")
    
    def remove_job(self, job_name: str):
        """Remove a keeper job"""
        if job_name in self.jobs:
            del self.jobs[job_name]
            logger.info(f"Removed keeper job: {job_name}")
    
    async def monitor_jobs(self):
        """Monitor and execute keeper jobs"""
        logger.info("Starting keeper job monitoring...")
        
        while True:
            try:
                for job_name, job in self.jobs.items():
                    if not job.active:
                        continue
                    
                    # Check if job should be executed
                    if self._should_execute_job(job):
                        await self._execute_job(job)
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in job monitoring: {str(e)}")
                await asyncio.sleep(60)
    
    def _should_execute_job(self, job: KeeperJob) -> bool:
        """Check if a job should be executed"""
        
        # Check frequency
        if job.last_execution:
            time_since_last = datetime.now() - job.last_execution
            if time_since_last.total_seconds() < job.frequency:
                return False
        
        # Check trigger condition
        return self._evaluate_trigger_condition(job)
    
    def _evaluate_trigger_condition(self, job: KeeperJob) -> bool:
        """Evaluate job trigger condition"""
        
        try:
            # Load target contract
            target_contract = self.w3.eth.contract(
                address=job.contract_address,
                abi=self._get_target_contract_abi(job.contract_address)
            )
            
            # Call checkUpkeep function
            if hasattr(target_contract.functions, 'checkUpkeep'):
                upkeep_needed, perform_data = target_contract.functions.checkUpkeep(
                    job.check_data
                ).call()
                return upkeep_needed
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating trigger condition for {job.name}: {str(e)}")
            return False
    
    def _get_target_contract_abi(self, contract_address: str) -> List[Dict]:
        """Get ABI for target contract"""
        # This would typically load from a registry or file
        # For now, return minimal upkeep ABI
        return [
            {
                "inputs": [{"name": "checkData", "type": "bytes"}],
                "name": "checkUpkeep",
                "outputs": [
                    {"name": "upkeepNeeded", "type": "bool"},
                    {"name": "performData", "type": "bytes"}
                ],
                "type": "function"
            },
            {
                "inputs": [{"name": "performData", "type": "bytes"}],
                "name": "performUpkeep",
                "outputs": [],
                "type": "function"
            }
        ]
    
    async def _execute_job(self, job: KeeperJob):
        """Execute a keeper job"""
        
        try:
            logger.info(f"Executing keeper job: {job.name}")
            
            # Load target contract
            target_contract = self.w3.eth.contract(
                address=job.contract_address,
                abi=self._get_target_contract_abi(job.contract_address)
            )
            
            # Get perform data
            _, perform_data = target_contract.functions.checkUpkeep(job.check_data).call()
            
            # Execute performUpkeep
            perform_tx = target_contract.functions.performUpkeep(perform_data).build_transaction({
                'from': self.account.address,
                'gas': job.gas_limit,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            signed_tx = self.account.sign_transaction(perform_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Update job execution time
            job.last_execution = datetime.now()
            
            logger.info(f"Job {job.name} executed successfully. Gas used: {receipt.gasUsed}")
            
        except Exception as e:
            logger.error(f"Failed to execute job {job.name}: {str(e)}")
    
    async def fund_upkeep(self, upkeep_id: int, amount: int):
        """Add funds to an upkeep"""
        
        try:
            # This would call addFunds function on the registry
            logger.info(f"Funding upkeep {upkeep_id} with {amount} LINK")
            
            # Implementation would go here
            pass
            
        except Exception as e:
            logger.error(f"Failed to fund upkeep: {str(e)}")
            raise
    
    async def pause_upkeep(self, upkeep_id: int):
        """Pause an upkeep"""
        
        try:
            logger.info(f"Pausing upkeep {upkeep_id}")
            
            # Implementation would call pauseUpkeep function
            pass
            
        except Exception as e:
            logger.error(f"Failed to pause upkeep: {str(e)}")
            raise
    
    async def unpause_upkeep(self, upkeep_id: int):
        """Unpause an upkeep"""
        
        try:
            logger.info(f"Unpausing upkeep {upkeep_id}")
            
            # Implementation would call unpauseUpkeep function
            pass
            
        except Exception as e:
            logger.error(f"Failed to unpause upkeep: {str(e)}")
            raise
    
    def get_job_status(self) -> Dict[str, Dict]:
        """Get status of all jobs"""
        
        status = {}
        for job_name, job in self.jobs.items():
            status[job_name] = {
                'active': job.active,
                'last_execution': job.last_execution.isoformat() if job.last_execution else None,
                'contract_address': job.contract_address,
                'function_name': job.function_name,
                'frequency': job.frequency
            }
        
        return status
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up Chainlink Keeper Manager...")
        # Cancel any running tasks, close connections, etc.
        pass

# Example usage
async def main():
    """Example usage of ChainlinkKeeperManager"""
    
    # Configuration
    web3_provider = os.getenv('INFURA_API_KEY', 'https://mainnet.infura.io/v3/YOUR_KEY')
    private_key = os.getenv('PRIVATE_KEY')
    keeper_registry = "0x02777053d6764996e594c3E88AF1D58D5363a2e6"  # Ethereum mainnet
    link_token = "0x514910771AF9Ca656af840dff83E8264EcF986CA"  # LINK token
    
    if not private_key:
        logger.error("PRIVATE_KEY environment variable not set")
        return
    
    # Initialize manager
    keeper_manager = ChainlinkKeeperManager(
        web3_provider=web3_provider,
        private_key=private_key,
        keeper_registry_address=keeper_registry,
        link_token_address=link_token
    )
    
    # Add example job
    rebalance_job = KeeperJob(
        name="vault_rebalance",
        contract_address="0x...",  # Your vault contract address
        function_name="rebalance",
        check_data=b'',
        gas_limit=500000,
        trigger_condition="time_based",
        frequency=86400  # Daily
    )
    
    keeper_manager.add_job(rebalance_job)
    
    # Start monitoring
    try:
        await keeper_manager.monitor_jobs()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await keeper_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
