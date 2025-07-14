"""
Multi-signature wallet service for enhanced security in DeFi operations.
Manages proposal creation, approval workflows, and execution of critical operations.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from web3 import Web3
from eth_account import Account
from eth_utils import to_checksum_address

logger = logging.getLogger(__name__)

class ProposalType(Enum):
    VAULT_DEPLOYMENT = "vault_deployment"
    STRATEGY_UPDATE = "strategy_update"
    PARAMETER_CHANGE = "parameter_change"
    EMERGENCY_ACTION = "emergency_action"
    FUND_WITHDRAWAL = "fund_withdrawal"
    UPGRADE_CONTRACT = "upgrade_contract"

class ProposalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"

@dataclass
class Proposal:
    """Multi-sig proposal"""
    id: str
    title: str
    description: str
    proposal_type: ProposalType
    target_contract: str
    function_data: bytes
    value: int  # ETH value
    proposer: str
    created_at: datetime
    expires_at: datetime
    status: ProposalStatus
    approvals: List[str]
    rejections: List[str]
    execution_hash: Optional[str] = None
    executed_at: Optional[datetime] = None

@dataclass
class Signer:
    """Multi-sig signer information"""
    address: str
    name: str
    role: str
    active: bool
    added_at: datetime

class MultisigService:
    """Multi-signature wallet service"""
    
    def __init__(self, web3_service, multisig_contract_address: str):
        self.web3_service = web3_service
        self.multisig_address = multisig_contract_address
        
        # Load multisig contract
        self.multisig_contract = None
        self._load_multisig_contract()
        
        # Configuration
        self.config = {
            'required_confirmations': 3,
            'proposal_expiry_hours': 72,  # 3 days
            'emergency_expiry_hours': 24,  # 1 day for emergency proposals
            'max_pending_proposals': 50
        }
        
        # State
        self.signers: Dict[str, Signer] = {}
        self.proposals: Dict[str, Proposal] = {}
        self.proposal_counter = 0
        
        # Load initial state
        asyncio.create_task(self._initialize_state())
    
    def _load_multisig_contract(self):
        """Load multi-sig contract"""
        
        # Minimal multisig ABI
        multisig_abi = [
            {
                "inputs": [
                    {"name": "destination", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "data", "type": "bytes"}
                ],
                "name": "submitTransaction",
                "outputs": [{"name": "transactionId", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "transactionId", "type": "uint256"}],
                "name": "confirmTransaction",
                "outputs": [],
                "type": "function"
            },
            {
                "inputs": [{"name": "transactionId", "type": "uint256"}],
                "name": "revokeConfirmation",
                "outputs": [],
                "type": "function"
            },
            {
                "inputs": [{"name": "transactionId", "type": "uint256"}],
                "name": "executeTransaction",
                "outputs": [],
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getOwners",
                "outputs": [{"name": "", "type": "address[]"}],
                "type": "function"
            },
            {
                "inputs": [],
                "name": "required",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        if self.web3_service.w3:
            self.multisig_contract = self.web3_service.w3.eth.contract(
                address=to_checksum_address(self.multisig_address),
                abi=multisig_abi
            )
    
    async def _initialize_state(self):
        """Initialize service state"""
        
        try:
            # Load signers from contract
            await self._load_signers()
            
            # Load configuration from contract
            await self._load_config()
            
            # Start monitoring
            asyncio.create_task(self._monitor_proposals())
            
            logger.info("Multisig service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize multisig service: {str(e)}")
    
    async def _load_signers(self):
        """Load signers from multisig contract"""
        
        try:
            if self.multisig_contract:
                owners = self.multisig_contract.functions.getOwners().call()
                
                for i, owner in enumerate(owners):
                    self.signers[owner] = Signer(
                        address=owner,
                        name=f"Signer {i+1}",
                        role="owner",
                        active=True,
                        added_at=datetime.now()  # Would get actual date from events
                    )
                
                logger.info(f"Loaded {len(self.signers)} signers")
        
        except Exception as e:
            logger.error(f"Failed to load signers: {str(e)}")
    
    async def _load_config(self):
        """Load configuration from contract"""
        
        try:
            if self.multisig_contract:
                required = self.multisig_contract.functions.required().call()
                self.config['required_confirmations'] = required
                
                logger.info(f"Required confirmations: {required}")
        
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")
    
    async def create_proposal(self,
                            title: str,
                            description: str,
                            proposal_type: ProposalType,
                            target_contract: str,
                            function_data: bytes,
                            value: int = 0,
                            proposer: str = None) -> str:
        """Create a new proposal"""
        
        # Validate proposer
        if proposer and proposer not in self.signers:
            raise ValueError("Proposer is not a valid signer")
        
        # Check proposal limits
        pending_count = len([p for p in self.proposals.values() if p.status == ProposalStatus.PENDING])
        if pending_count >= self.config['max_pending_proposals']:
            raise ValueError("Maximum pending proposals reached")
        
        # Generate proposal ID
        self.proposal_counter += 1
        proposal_id = f"proposal_{self.proposal_counter}_{int(datetime.now().timestamp())}"
        
        # Set expiry based on type
        if proposal_type == ProposalType.EMERGENCY_ACTION:
            expiry_hours = self.config['emergency_expiry_hours']
        else:
            expiry_hours = self.config['proposal_expiry_hours']
        
        expires_at = datetime.now() + timedelta(hours=expiry_hours)
        
        # Create proposal
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposal_type=proposal_type,
            target_contract=target_contract,
            function_data=function_data,
            value=value,
            proposer=proposer or "system",
            created_at=datetime.now(),
            expires_at=expires_at,
            status=ProposalStatus.PENDING,
            approvals=[],
            rejections=[]
        )
        
        # Store proposal
        self.proposals[proposal_id] = proposal
        
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal_id
    
    async def approve_proposal(self, proposal_id: str, signer: str) -> bool:
        """Approve a proposal"""
        
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
        
        if signer not in self.signers:
            raise ValueError("Invalid signer")
        
        proposal = self.proposals[proposal_id]
        
        # Check proposal status
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError("Proposal is not pending")
        
        # Check expiry
        if datetime.now() > proposal.expires_at:
            proposal.status = ProposalStatus.EXPIRED
            raise ValueError("Proposal has expired")
        
        # Check if already approved/rejected by this signer
        if signer in proposal.approvals:
            raise ValueError("Already approved by this signer")
        
        if signer in proposal.rejections:
            # Remove from rejections if switching to approval
            proposal.rejections.remove(signer)
        
        # Add approval
        proposal.approvals.append(signer)
        
        # Check if enough approvals
        if len(proposal.approvals) >= self.config['required_confirmations']:
            proposal.status = ProposalStatus.APPROVED
            
            # Auto-execute if possible
            if await self._can_auto_execute(proposal):
                await self._execute_proposal(proposal)
        
        logger.info(f"Proposal {proposal_id} approved by {signer} ({len(proposal.approvals)}/{self.config['required_confirmations']})")
        return proposal.status == ProposalStatus.APPROVED
    
    async def reject_proposal(self, proposal_id: str, signer: str) -> bool:
        """Reject a proposal"""
        
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
        
        if signer not in self.signers:
            raise ValueError("Invalid signer")
        
        proposal = self.proposals[proposal_id]
        
        # Check proposal status
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError("Proposal is not pending")
        
        # Check if already rejected/approved by this signer
        if signer in proposal.rejections:
            raise ValueError("Already rejected by this signer")
        
        if signer in proposal.approvals:
            # Remove from approvals if switching to rejection
            proposal.approvals.remove(signer)
        
        # Add rejection
        proposal.rejections.append(signer)
        
        # Check if enough rejections to reject proposal
        max_rejections = len(self.signers) - self.config['required_confirmations'] + 1
        if len(proposal.rejections) >= max_rejections:
            proposal.status = ProposalStatus.REJECTED
        
        logger.info(f"Proposal {proposal_id} rejected by {signer}")
        return proposal.status == ProposalStatus.REJECTED
    
    async def execute_proposal(self, proposal_id: str, executor: str = None) -> str:
        """Execute an approved proposal"""
        
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found")
        
        proposal = self.proposals[proposal_id]
        
        # Check if proposal can be executed
        if proposal.status != ProposalStatus.APPROVED:
            raise ValueError("Proposal is not approved")
        
        if datetime.now() > proposal.expires_at:
            proposal.status = ProposalStatus.EXPIRED
            raise ValueError("Proposal has expired")
        
        return await self._execute_proposal(proposal, executor)
    
    async def _execute_proposal(self, proposal: Proposal, executor: str = None) -> str:
        """Internal proposal execution"""
        
        try:
            logger.info(f"Executing proposal {proposal.id}: {proposal.title}")
            
            # Submit transaction to multisig contract
            if self.multisig_contract:
                submit_function = self.multisig_contract.functions.submitTransaction(
                    to_checksum_address(proposal.target_contract),
                    proposal.value,
                    proposal.function_data
                )
                
                # Execute transaction
                result = await self.web3_service.send_transaction(submit_function)
                
                if result.status:
                    proposal.execution_hash = result.hash
                    proposal.executed_at = datetime.now()
                    proposal.status = ProposalStatus.EXECUTED
                    
                    logger.info(f"Proposal {proposal.id} executed successfully: {result.hash}")
                    return result.hash
                else:
                    raise Exception("Transaction failed")
            else:
                raise Exception("Multisig contract not available")
        
        except Exception as e:
            logger.error(f"Failed to execute proposal {proposal.id}: {str(e)}")
            raise
    
    async def _can_auto_execute(self, proposal: Proposal) -> bool:
        """Check if proposal can be auto-executed"""
        
        # Emergency actions should be executed immediately
        if proposal.proposal_type == ProposalType.EMERGENCY_ACTION:
            return True
        
        # Other proposals can be configured for auto-execution
        return False
    
    async def _monitor_proposals(self):
        """Monitor proposals for expiry and status changes"""
        
        while True:
            try:
                current_time = datetime.now()
                
                for proposal in self.proposals.values():
                    if proposal.status == ProposalStatus.PENDING and current_time > proposal.expires_at:
                        proposal.status = ProposalStatus.EXPIRED
                        logger.info(f"Proposal {proposal.id} expired")
                
                # Wait 1 minute before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in proposal monitoring: {str(e)}")
                await asyncio.sleep(60)
    
    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a specific proposal"""
        return self.proposals.get(proposal_id)
    
    def get_proposals(self, 
                     status: Optional[ProposalStatus] = None,
                     proposal_type: Optional[ProposalType] = None,
                     limit: int = 100) -> List[Proposal]:
        """Get proposals with optional filtering"""
        
        proposals = list(self.proposals.values())
        
        # Filter by status
        if status:
            proposals = [p for p in proposals if p.status == status]
        
        # Filter by type
        if proposal_type:
            proposals = [p for p in proposals if p.proposal_type == proposal_type]
        
        # Sort by creation date (newest first)
        proposals.sort(key=lambda x: x.created_at, reverse=True)
        
        return proposals[:limit]
    
    def get_pending_proposals(self) -> List[Proposal]:
        """Get all pending proposals"""
        return self.get_proposals(status=ProposalStatus.PENDING)
    
    def get_signer_info(self, address: str) -> Optional[Signer]:
        """Get signer information"""
        return self.signers.get(address)
    
    def get_all_signers(self) -> List[Signer]:
        """Get all signers"""
        return list(self.signers.values())
    
    def get_proposal_status_summary(self) -> Dict[str, int]:
        """Get summary of proposal statuses"""
        
        summary = {}
        for status in ProposalStatus:
            summary[status.value] = len([
                p for p in self.proposals.values() if p.status == status
            ])
        
        return summary
    
    async def create_emergency_proposal(self,
                                      title: str,
                                      description: str,
                                      target_contract: str,
                                      function_data: bytes,
                                      proposer: str) -> str:
        """Create an emergency proposal with shorter expiry"""
        
        return await self.create_proposal(
            title=f"EMERGENCY: {title}",
            description=description,
            proposal_type=ProposalType.EMERGENCY_ACTION,
            target_contract=target_contract,
            function_data=function_data,
            proposer=proposer
        )
    
    async def create_vault_deployment_proposal(self,
                                             vault_name: str,
                                             asset_address: str,
                                             risk_profile: int,
                                             proposer: str) -> str:
        """Create a vault deployment proposal"""
        
        # Encode function data for vault deployment
        function_data = self.web3_service.w3.keccak(text="deployVault(address,string,string,uint8,address)")[:4]
        # Would properly encode parameters
        
        return await self.create_proposal(
            title=f"Deploy Vault: {vault_name}",
            description=f"Deploy new yield vault for asset {asset_address} with risk profile {risk_profile}",
            proposal_type=ProposalType.VAULT_DEPLOYMENT,
            target_contract="0x...",  # Vault factory address
            function_data=function_data,
            proposer=proposer
        )
    
    def get_multisig_stats(self) -> Dict[str, Any]:
        """Get multisig statistics"""
        
        return {
            'total_signers': len(self.signers),
            'active_signers': len([s for s in self.signers.values() if s.active]),
            'required_confirmations': self.config['required_confirmations'],
            'total_proposals': len(self.proposals),
            'pending_proposals': len(self.get_pending_proposals()),
            'proposal_status_summary': self.get_proposal_status_summary(),
            'multisig_address': self.multisig_address
        }
