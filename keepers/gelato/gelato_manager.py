"""
Gelato Network integration for automated DeFi yield farming operations.
Provides alternative automation solution with different features and pricing.
"""

import asyncio
import json
import logging
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from web3 import Web3
from web3.contract import Contract
from eth_account import Account
import os
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class GelatoTask:
    """Represents a Gelato automation task"""
    name: str
    target_contract: str
    function_selector: str
    resolver_contract: str
    resolver_data: bytes
    interval: int  # seconds
    max_fee: int  # in wei
    active: bool = True
    task_id: Optional[str] = None
    created_at: Optional[datetime] = None
    last_execution: Optional[datetime] = None

@dataclass
class TaskExecution:
    """Task execution information"""
    task_id: str
    execution_time: datetime
    gas_used: int
    fee_paid: int
    success: bool
    error_message: Optional[str] = None

class GelatoManager:
    """Manages Gelato Network automation tasks"""
    
    def __init__(self,
                 web3_provider: str,
                 private_key: str,
                 gelato_relay_api_key: str,
                 gelato_ops_address: str = None):
        
        self.w3 = Web3(Web3.HTTPProvider(web3_provider))
        self.account = Account.from_key(private_key)
        self.api_key = gelato_relay_api_key
        
        # Gelato Ops contract address (mainnet)
        self.gelato_ops_address = gelato_ops_address or "0xB3f5503f93d5Ef84b06993a1975B9D21B962892F"
        
        # API endpoints
        self.api_base_url = "https://relay.gelato.digital"
        self.ops_api_url = "https://api.gelato.digital"
        
        # Load Gelato Ops ABI
        self.gelato_ops_abi = self._get_gelato_ops_abi()
        self.gelato_ops = self.w3.eth.contract(
            address=self.gelato_ops_address,
            abi=self.gelato_ops_abi
        )
        
        # Task management
        self.tasks: Dict[str, GelatoTask] = {}
        self.executions: List[TaskExecution] = []
        
        logger.info(f"Initialized Gelato Manager for account: {self.account.address}")
    
    def _get_gelato_ops_abi(self) -> List[Dict]:
        """Get Gelato Ops contract ABI"""
        return [
            {
                "inputs": [
                    {"name": "execAddress", "type": "address"},
                    {"name": "execData", "type": "bytes"},
                    {"name": "resolverAddress", "type": "address"},
                    {"name": "resolverData", "type": "bytes"}
                ],
                "name": "createTask",
                "outputs": [{"name": "taskId", "type": "bytes32"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "taskId", "type": "bytes32"}],
                "name": "cancelTask",
                "outputs": [],
                "type": "function"
            },
            {
                "inputs": [{"name": "taskId", "type": "bytes32"}],
                "name": "getTaskId",
                "outputs": [{"name": "", "type": "bytes32"}],
                "type": "function"
            }
        ]
    
    async def create_task(self, task: GelatoTask) -> str:
        """Create a new Gelato automation task"""
        
        try:
            logger.info(f"Creating Gelato task: {task.name}")
            
            # Prepare function data
            function_data = self.w3.keccak(text=task.function_selector)[:4]
            
            # Create task transaction
            create_tx = self.gelato_ops.functions.createTask(
                task.target_contract,
                function_data,
                task.resolver_contract,
                task.resolver_data
            ).build_transaction({
                'from': self.account.address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_tx = self.account.sign_transaction(create_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Extract task ID from logs
            task_id = self._extract_task_id_from_receipt(receipt)
            
            # Update task
            task.task_id = task_id
            task.created_at = datetime.now()
            self.tasks[task.name] = task
            
            logger.info(f"Task created successfully. ID: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create task: {str(e)}")
            raise
    
    def _extract_task_id_from_receipt(self, receipt) -> str:
        """Extract task ID from transaction receipt"""
        # Parse logs to find TaskCreated event
        # For now, return a placeholder
        return f"task_{datetime.now().timestamp()}"
    
    async def cancel_task(self, task_name: str):
        """Cancel a Gelato task"""
        
        if task_name not in self.tasks:
            raise ValueError(f"Task {task_name} not found")
        
        task = self.tasks[task_name]
        if not task.task_id:
            raise ValueError(f"Task {task_name} has no task ID")
        
        try:
            logger.info(f"Cancelling task: {task_name}")
            
            # Cancel task transaction
            cancel_tx = self.gelato_ops.functions.cancelTask(
                task.task_id.encode() if isinstance(task.task_id, str) else task.task_id
            ).build_transaction({
                'from': self.account.address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_tx = self.account.sign_transaction(cancel_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Update task status
            task.active = False
            
            logger.info(f"Task {task_name} cancelled successfully")
            
        except Exception as e:
            logger.error(f"Failed to cancel task: {str(e)}")
            raise
    
    async def submit_relay_request(self, 
                                 target_contract: str,
                                 function_data: bytes,
                                 fee_token: str = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE") -> str:
        """Submit a relay request to Gelato"""
        
        try:
            # Prepare relay request
            relay_request = {
                "chainId": self.w3.eth.chain_id,
                "target": target_contract,
                "data": function_data.hex(),
                "feeToken": fee_token,
                "gas": "500000"
            }
            
            # Submit to Gelato Relay API
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    f"{self.api_base_url}/relays/v2/call",
                    json=relay_request,
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        task_id = result.get("taskId")
                        logger.info(f"Relay request submitted. Task ID: {task_id}")
                        return task_id
                    else:
                        error_text = await response.text()
                        raise Exception(f"Relay request failed: {error_text}")
        
        except Exception as e:
            logger.error(f"Failed to submit relay request: {str(e)}")
            raise
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a Gelato task"""
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                
                async with session.get(
                    f"{self.ops_api_url}/tasks/{task_id}/status",
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Failed to get task status: {error_text}")
        
        except Exception as e:
            logger.error(f"Failed to get task status: {str(e)}")
            raise
    
    async def monitor_tasks(self):
        """Monitor Gelato tasks and track executions"""
        logger.info("Starting Gelato task monitoring...")
        
        while True:
            try:
                for task_name, task in self.tasks.items():
                    if not task.active or not task.task_id:
                        continue
                    
                    # Check task status
                    status = await self.get_task_status(task.task_id)
                    
                    # Process status updates
                    await self._process_task_status(task, status)
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in task monitoring: {str(e)}")
                await asyncio.sleep(30)
    
    async def _process_task_status(self, task: GelatoTask, status: Dict[str, Any]):
        """Process task status update"""
        
        # Check for new executions
        executions = status.get("executions", [])
        
        for execution in executions:
            execution_time = datetime.fromisoformat(execution.get("timestamp", ""))
            
            # Check if this is a new execution
            if not task.last_execution or execution_time > task.last_execution:
                
                # Record execution
                task_execution = TaskExecution(
                    task_id=task.task_id,
                    execution_time=execution_time,
                    gas_used=execution.get("gasUsed", 0),
                    fee_paid=execution.get("feePaid", 0),
                    success=execution.get("success", False),
                    error_message=execution.get("error")
                )
                
                self.executions.append(task_execution)
                task.last_execution = execution_time
                
                logger.info(f"Task {task.name} executed at {execution_time}. "
                           f"Success: {task_execution.success}")
    
    def add_task(self, task: GelatoTask):
        """Add a task to management"""
        self.tasks[task.name] = task
        logger.info(f"Added Gelato task: {task.name}")
    
    def remove_task(self, task_name: str):
        """Remove a task from management"""
        if task_name in self.tasks:
            del self.tasks[task_name]
            logger.info(f"Removed Gelato task: {task_name}")
    
    def get_task_summary(self) -> Dict[str, Any]:
        """Get summary of all tasks"""
        
        summary = {
            "total_tasks": len(self.tasks),
            "active_tasks": sum(1 for task in self.tasks.values() if task.active),
            "total_executions": len(self.executions),
            "successful_executions": sum(1 for exec in self.executions if exec.success),
            "tasks": {}
        }
        
        for task_name, task in self.tasks.items():
            task_executions = [e for e in self.executions if e.task_id == task.task_id]
            
            summary["tasks"][task_name] = {
                "active": task.active,
                "task_id": task.task_id,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "last_execution": task.last_execution.isoformat() if task.last_execution else None,
                "execution_count": len(task_executions),
                "success_rate": (
                    sum(1 for e in task_executions if e.success) / len(task_executions)
                    if task_executions else 0
                )
            }
        
        return summary
    
    async def deposit_funds(self, amount: int):
        """Deposit funds to Gelato for task execution"""
        
        try:
            logger.info(f"Depositing {amount} wei to Gelato")
            
            # This would interact with Gelato's treasury contract
            # Implementation depends on specific Gelato version
            
            # Placeholder implementation
            pass
            
        except Exception as e:
            logger.error(f"Failed to deposit funds: {str(e)}")
            raise
    
    async def withdraw_funds(self, amount: int):
        """Withdraw funds from Gelato"""
        
        try:
            logger.info(f"Withdrawing {amount} wei from Gelato")
            
            # This would interact with Gelato's treasury contract
            # Implementation depends on specific Gelato version
            
            # Placeholder implementation
            pass
            
        except Exception as e:
            logger.error(f"Failed to withdraw funds: {str(e)}")
            raise
    
    async def get_balance(self) -> int:
        """Get current balance in Gelato"""
        
        try:
            # This would query Gelato's treasury contract
            # For now, return placeholder
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get balance: {str(e)}")
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up Gelato Manager...")
        
        # Cancel all active tasks
        for task_name, task in self.tasks.items():
            if task.active and task.task_id:
                try:
                    await self.cancel_task(task_name)
                except Exception as e:
                    logger.error(f"Failed to cancel task {task_name}: {str(e)}")

# Example usage
async def main():
    """Example usage of GelatoManager"""
    
    # Configuration
    web3_provider = os.getenv('INFURA_API_KEY', 'https://mainnet.infura.io/v3/YOUR_KEY')
    private_key = os.getenv('PRIVATE_KEY')
    gelato_api_key = os.getenv('GELATO_RELAY_API_KEY')
    
    if not all([private_key, gelato_api_key]):
        logger.error("Required environment variables not set")
        return
    
    # Initialize manager
    gelato_manager = GelatoManager(
        web3_provider=web3_provider,
        private_key=private_key,
        gelato_relay_api_key=gelato_api_key
    )
    
    # Create example task
    harvest_task = GelatoTask(
        name="yield_harvest",
        target_contract="0x...",  # Your vault contract
        function_selector="harvestYield()",
        resolver_contract="0x...",  # Resolver contract
        resolver_data=b'',
        interval=3600,  # 1 hour
        max_fee=10**16  # 0.01 ETH
    )
    
    gelato_manager.add_task(harvest_task)
    
    # Create the task
    try:
        task_id = await gelato_manager.create_task(harvest_task)
        logger.info(f"Created task with ID: {task_id}")
        
        # Start monitoring
        await gelato_manager.monitor_tasks()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await gelato_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
