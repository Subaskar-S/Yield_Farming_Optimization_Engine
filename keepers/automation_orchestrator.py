"""
Automation orchestrator for DeFi yield farming operations.
Manages both Chainlink Keepers and Gelato Network integrations.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import json
import os

from chainlink.keeper_manager import ChainlinkKeeperManager, KeeperJob
from gelato.gelato_manager import GelatoManager, GelatoTask

logger = logging.getLogger(__name__)

class AutomationProvider(Enum):
    CHAINLINK = "chainlink"
    GELATO = "gelato"
    AUTO = "auto"  # Automatically choose best provider

@dataclass
class AutomationJob:
    """Unified automation job configuration"""
    name: str
    target_contract: str
    function_name: str
    check_data: bytes
    gas_limit: int
    frequency: int  # seconds
    max_fee: int  # maximum fee willing to pay
    priority: int = 1  # 1=low, 2=medium, 3=high
    provider: AutomationProvider = AutomationProvider.AUTO
    active: bool = True
    created_at: Optional[datetime] = None
    last_execution: Optional[datetime] = None

@dataclass
class ExecutionMetrics:
    """Execution metrics for performance tracking"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_gas_used: int = 0
    total_fees_paid: int = 0
    average_execution_time: float = 0.0
    last_execution_time: Optional[datetime] = None

class AutomationOrchestrator:
    """Orchestrates automation across multiple providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Initialize providers
        self.chainlink_manager = None
        self.gelato_manager = None
        
        # Job management
        self.jobs: Dict[str, AutomationJob] = {}
        self.job_assignments: Dict[str, AutomationProvider] = {}
        self.metrics: Dict[str, ExecutionMetrics] = {}
        
        # Provider costs (gas price in gwei)
        self.provider_costs = {
            AutomationProvider.CHAINLINK: 20,  # Base cost
            AutomationProvider.GELATO: 25     # Slightly higher but more features
        }
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize automation providers"""
        
        # Initialize Chainlink Keepers if configured
        if self.config.get('chainlink', {}).get('enabled', False):
            try:
                self.chainlink_manager = ChainlinkKeeperManager(
                    web3_provider=self.config['chainlink']['web3_provider'],
                    private_key=self.config['chainlink']['private_key'],
                    keeper_registry_address=self.config['chainlink']['registry_address'],
                    link_token_address=self.config['chainlink']['link_token_address']
                )
                logger.info("Chainlink Keepers initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Chainlink Keepers: {str(e)}")
        
        # Initialize Gelato if configured
        if self.config.get('gelato', {}).get('enabled', False):
            try:
                self.gelato_manager = GelatoManager(
                    web3_provider=self.config['gelato']['web3_provider'],
                    private_key=self.config['gelato']['private_key'],
                    gelato_relay_api_key=self.config['gelato']['api_key']
                )
                logger.info("Gelato Network initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Gelato Network: {str(e)}")
    
    def add_job(self, job: AutomationJob):
        """Add an automation job"""
        
        # Initialize metrics
        self.metrics[job.name] = ExecutionMetrics()
        
        # Determine best provider
        if job.provider == AutomationProvider.AUTO:
            job.provider = self._select_best_provider(job)
        
        # Store job
        self.jobs[job.name] = job
        self.job_assignments[job.name] = job.provider
        
        logger.info(f"Added job {job.name} with provider {job.provider.value}")
    
    def _select_best_provider(self, job: AutomationJob) -> AutomationProvider:
        """Select the best provider for a job based on various factors"""
        
        scores = {}
        
        # Score Chainlink
        if self.chainlink_manager:
            chainlink_score = 0
            
            # Cost factor (lower is better)
            chainlink_cost = self.provider_costs[AutomationProvider.CHAINLINK] * job.gas_limit
            chainlink_score += max(0, 100 - (chainlink_cost / 1000))
            
            # Reliability factor
            chainlink_score += 90  # High reliability
            
            # Feature factor
            if job.frequency >= 3600:  # Hourly or less frequent
                chainlink_score += 20
            
            scores[AutomationProvider.CHAINLINK] = chainlink_score
        
        # Score Gelato
        if self.gelato_manager:
            gelato_score = 0
            
            # Cost factor
            gelato_cost = self.provider_costs[AutomationProvider.GELATO] * job.gas_limit
            gelato_score += max(0, 100 - (gelato_cost / 1000))
            
            # Reliability factor
            gelato_score += 85  # Good reliability
            
            # Feature factor (better for frequent tasks)
            if job.frequency < 3600:  # More frequent than hourly
                gelato_score += 25
            
            # Priority factor
            if job.priority >= 2:
                gelato_score += 15
            
            scores[AutomationProvider.GELATO] = gelato_score
        
        # Select provider with highest score
        if not scores:
            raise ValueError("No automation providers available")
        
        best_provider = max(scores.keys(), key=lambda k: scores[k])
        logger.info(f"Selected {best_provider.value} for job {job.name} (score: {scores[best_provider]})")
        
        return best_provider
    
    async def deploy_job(self, job_name: str):
        """Deploy a job to its assigned provider"""
        
        if job_name not in self.jobs:
            raise ValueError(f"Job {job_name} not found")
        
        job = self.jobs[job_name]
        provider = self.job_assignments[job_name]
        
        try:
            if provider == AutomationProvider.CHAINLINK:
                await self._deploy_chainlink_job(job)
            elif provider == AutomationProvider.GELATO:
                await self._deploy_gelato_job(job)
            
            job.created_at = datetime.now()
            logger.info(f"Job {job_name} deployed successfully to {provider.value}")
            
        except Exception as e:
            logger.error(f"Failed to deploy job {job_name}: {str(e)}")
            raise
    
    async def _deploy_chainlink_job(self, job: AutomationJob):
        """Deploy job to Chainlink Keepers"""
        
        if not self.chainlink_manager:
            raise ValueError("Chainlink Keepers not initialized")
        
        # Convert to Chainlink job format
        keeper_job = KeeperJob(
            name=job.name,
            contract_address=job.target_contract,
            function_name=job.function_name,
            check_data=job.check_data,
            gas_limit=job.gas_limit,
            trigger_condition="time_based",
            frequency=job.frequency
        )
        
        # Register upkeep
        upkeep_id = await self.chainlink_manager.register_upkeep(
            name=job.name,
            target_contract=job.target_contract,
            gas_limit=job.gas_limit,
            check_data=job.check_data
        )
        
        # Add to manager
        self.chainlink_manager.add_job(keeper_job)
    
    async def _deploy_gelato_job(self, job: AutomationJob):
        """Deploy job to Gelato Network"""
        
        if not self.gelato_manager:
            raise ValueError("Gelato Network not initialized")
        
        # Convert to Gelato task format
        gelato_task = GelatoTask(
            name=job.name,
            target_contract=job.target_contract,
            function_selector=f"{job.function_name}()",
            resolver_contract=job.target_contract,  # Assuming same contract
            resolver_data=job.check_data,
            interval=job.frequency,
            max_fee=job.max_fee
        )
        
        # Create task
        task_id = await self.gelato_manager.create_task(gelato_task)
        
        # Add to manager
        self.gelato_manager.add_task(gelato_task)
    
    async def cancel_job(self, job_name: str):
        """Cancel a deployed job"""
        
        if job_name not in self.jobs:
            raise ValueError(f"Job {job_name} not found")
        
        provider = self.job_assignments[job_name]
        
        try:
            if provider == AutomationProvider.CHAINLINK:
                self.chainlink_manager.remove_job(job_name)
            elif provider == AutomationProvider.GELATO:
                await self.gelato_manager.cancel_task(job_name)
            
            # Update job status
            self.jobs[job_name].active = False
            
            logger.info(f"Job {job_name} cancelled successfully")
            
        except Exception as e:
            logger.error(f"Failed to cancel job {job_name}: {str(e)}")
            raise
    
    async def monitor_all_jobs(self):
        """Monitor all jobs across providers"""
        logger.info("Starting unified job monitoring...")
        
        # Start provider-specific monitoring
        monitoring_tasks = []
        
        if self.chainlink_manager:
            monitoring_tasks.append(
                asyncio.create_task(self.chainlink_manager.monitor_jobs())
            )
        
        if self.gelato_manager:
            monitoring_tasks.append(
                asyncio.create_task(self.gelato_manager.monitor_tasks())
            )
        
        # Start metrics collection
        monitoring_tasks.append(
            asyncio.create_task(self._collect_metrics())
        )
        
        # Wait for all monitoring tasks
        try:
            await asyncio.gather(*monitoring_tasks)
        except Exception as e:
            logger.error(f"Error in job monitoring: {str(e)}")
    
    async def _collect_metrics(self):
        """Collect execution metrics from all providers"""
        
        while True:
            try:
                # Update metrics from Chainlink
                if self.chainlink_manager:
                    chainlink_status = self.chainlink_manager.get_job_status()
                    self._update_metrics_from_chainlink(chainlink_status)
                
                # Update metrics from Gelato
                if self.gelato_manager:
                    gelato_summary = self.gelato_manager.get_task_summary()
                    self._update_metrics_from_gelato(gelato_summary)
                
                # Wait before next collection
                await asyncio.sleep(60)  # Collect every minute
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {str(e)}")
                await asyncio.sleep(60)
    
    def _update_metrics_from_chainlink(self, status: Dict[str, Dict]):
        """Update metrics from Chainlink status"""
        
        for job_name, job_status in status.items():
            if job_name in self.metrics:
                metrics = self.metrics[job_name]
                
                # Update last execution time
                if job_status.get('last_execution'):
                    last_exec = datetime.fromisoformat(job_status['last_execution'])
                    if not metrics.last_execution_time or last_exec > metrics.last_execution_time:
                        metrics.last_execution_time = last_exec
                        metrics.total_executions += 1
                        metrics.successful_executions += 1  # Assume success for now
    
    def _update_metrics_from_gelato(self, summary: Dict[str, Any]):
        """Update metrics from Gelato summary"""
        
        for job_name, task_info in summary.get('tasks', {}).items():
            if job_name in self.metrics:
                metrics = self.metrics[job_name]
                
                # Update execution count
                execution_count = task_info.get('execution_count', 0)
                if execution_count > metrics.total_executions:
                    new_executions = execution_count - metrics.total_executions
                    metrics.total_executions = execution_count
                    
                    # Update success count based on success rate
                    success_rate = task_info.get('success_rate', 1.0)
                    metrics.successful_executions = int(execution_count * success_rate)
                    metrics.failed_executions = execution_count - metrics.successful_executions
                
                # Update last execution time
                if task_info.get('last_execution'):
                    metrics.last_execution_time = datetime.fromisoformat(task_info['last_execution'])
    
    def get_job_status(self) -> Dict[str, Any]:
        """Get status of all jobs"""
        
        status = {
            'total_jobs': len(self.jobs),
            'active_jobs': sum(1 for job in self.jobs.values() if job.active),
            'provider_distribution': {},
            'jobs': {}
        }
        
        # Count jobs by provider
        for provider in self.job_assignments.values():
            status['provider_distribution'][provider.value] = (
                status['provider_distribution'].get(provider.value, 0) + 1
            )
        
        # Job details
        for job_name, job in self.jobs.items():
            metrics = self.metrics.get(job_name, ExecutionMetrics())
            
            status['jobs'][job_name] = {
                'active': job.active,
                'provider': self.job_assignments[job_name].value,
                'target_contract': job.target_contract,
                'function_name': job.function_name,
                'frequency': job.frequency,
                'priority': job.priority,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'metrics': {
                    'total_executions': metrics.total_executions,
                    'successful_executions': metrics.successful_executions,
                    'failed_executions': metrics.failed_executions,
                    'success_rate': (
                        metrics.successful_executions / metrics.total_executions
                        if metrics.total_executions > 0 else 0
                    ),
                    'total_gas_used': metrics.total_gas_used,
                    'total_fees_paid': metrics.total_fees_paid,
                    'last_execution': (
                        metrics.last_execution_time.isoformat()
                        if metrics.last_execution_time else None
                    )
                }
            }
        
        return status
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        
        total_executions = sum(m.total_executions for m in self.metrics.values())
        total_successful = sum(m.successful_executions for m in self.metrics.values())
        total_gas = sum(m.total_gas_used for m in self.metrics.values())
        total_fees = sum(m.total_fees_paid for m in self.metrics.values())
        
        return {
            'overall_metrics': {
                'total_executions': total_executions,
                'overall_success_rate': total_successful / total_executions if total_executions > 0 else 0,
                'total_gas_used': total_gas,
                'total_fees_paid': total_fees,
                'average_gas_per_execution': total_gas / total_executions if total_executions > 0 else 0
            },
            'provider_performance': {
                provider.value: {
                    'job_count': sum(
                        1 for p in self.job_assignments.values() if p == provider
                    ),
                    'estimated_cost_efficiency': self.provider_costs[provider]
                }
                for provider in [AutomationProvider.CHAINLINK, AutomationProvider.GELATO]
                if provider in self.provider_costs
            },
            'job_metrics': {
                job_name: {
                    'executions': metrics.total_executions,
                    'success_rate': (
                        metrics.successful_executions / metrics.total_executions
                        if metrics.total_executions > 0 else 0
                    ),
                    'gas_efficiency': (
                        metrics.total_gas_used / metrics.total_executions
                        if metrics.total_executions > 0 else 0
                    )
                }
                for job_name, metrics in self.metrics.items()
            }
        }
    
    async def cleanup(self):
        """Cleanup all resources"""
        logger.info("Cleaning up Automation Orchestrator...")
        
        # Cancel all active jobs
        for job_name, job in self.jobs.items():
            if job.active:
                try:
                    await self.cancel_job(job_name)
                except Exception as e:
                    logger.error(f"Failed to cancel job {job_name}: {str(e)}")
        
        # Cleanup providers
        if self.chainlink_manager:
            await self.chainlink_manager.cleanup()
        
        if self.gelato_manager:
            await self.gelato_manager.cleanup()

# Example usage
async def main():
    """Example usage of AutomationOrchestrator"""
    
    config = {
        'chainlink': {
            'enabled': True,
            'web3_provider': os.getenv('INFURA_API_KEY'),
            'private_key': os.getenv('PRIVATE_KEY'),
            'registry_address': '0x02777053d6764996e594c3E88AF1D58D5363a2e6',
            'link_token_address': '0x514910771AF9Ca656af840dff83E8264EcF986CA'
        },
        'gelato': {
            'enabled': True,
            'web3_provider': os.getenv('INFURA_API_KEY'),
            'private_key': os.getenv('PRIVATE_KEY'),
            'api_key': os.getenv('GELATO_RELAY_API_KEY')
        }
    }
    
    # Initialize orchestrator
    orchestrator = AutomationOrchestrator(config)
    
    # Add jobs
    rebalance_job = AutomationJob(
        name="vault_rebalance",
        target_contract="0x...",
        function_name="rebalance",
        check_data=b'',
        gas_limit=500000,
        frequency=86400,  # Daily
        max_fee=10**17,   # 0.1 ETH
        priority=2
    )
    
    harvest_job = AutomationJob(
        name="yield_harvest",
        target_contract="0x...",
        function_name="harvestYield",
        check_data=b'',
        gas_limit=300000,
        frequency=3600,   # Hourly
        max_fee=5*10**16, # 0.05 ETH
        priority=3
    )
    
    orchestrator.add_job(rebalance_job)
    orchestrator.add_job(harvest_job)
    
    # Deploy jobs
    await orchestrator.deploy_job("vault_rebalance")
    await orchestrator.deploy_job("yield_harvest")
    
    # Start monitoring
    try:
        await orchestrator.monitor_all_jobs()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
