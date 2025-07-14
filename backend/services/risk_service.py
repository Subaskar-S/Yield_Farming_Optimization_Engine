"""
Risk assessment and management service for DeFi yield farming platform.
Implements comprehensive risk monitoring, scoring, and mitigation strategies.
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskCategory(Enum):
    MARKET = "market"
    LIQUIDITY = "liquidity"
    SMART_CONTRACT = "smart_contract"
    PROTOCOL = "protocol"
    OPERATIONAL = "operational"
    REGULATORY = "regulatory"

@dataclass
class RiskMetric:
    """Individual risk metric"""
    name: str
    category: RiskCategory
    value: float
    threshold: float
    level: RiskLevel
    description: str
    timestamp: datetime

@dataclass
class RiskAssessment:
    """Comprehensive risk assessment"""
    protocol: str
    overall_score: float
    overall_level: RiskLevel
    metrics: List[RiskMetric]
    recommendations: List[str]
    timestamp: datetime

@dataclass
class RiskAlert:
    """Risk alert notification"""
    id: str
    protocol: str
    category: RiskCategory
    level: RiskLevel
    message: str
    metric_value: float
    threshold: float
    timestamp: datetime
    acknowledged: bool = False

class RiskService:
    """Comprehensive risk assessment and management service"""
    
    def __init__(self, web3_service, ml_service):
        self.web3_service = web3_service
        self.ml_service = ml_service
        
        # Risk configuration
        self.risk_config = self._load_risk_config()
        
        # Risk thresholds
        self.thresholds = {
            RiskLevel.LOW: 25,
            RiskLevel.MEDIUM: 50,
            RiskLevel.HIGH: 75,
            RiskLevel.CRITICAL: 90
        }
        
        # Active alerts
        self.active_alerts: Dict[str, RiskAlert] = {}
        
        # Risk history
        self.risk_history: List[RiskAssessment] = []
        
        # Monitoring state
        self.monitoring_active = False
        
        # Risk metrics cache
        self.metrics_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def _load_risk_config(self) -> Dict[str, Any]:
        """Load risk assessment configuration"""
        
        default_config = {
            "market_risk": {
                "volatility_threshold": 0.3,
                "correlation_threshold": 0.8,
                "liquidity_threshold": 1000000,  # $1M minimum
                "price_impact_threshold": 0.05
            },
            "protocol_risk": {
                "tvl_threshold": 10000000,  # $10M minimum
                "age_threshold": 90,  # 90 days minimum
                "audit_required": True,
                "governance_score_threshold": 70
            },
            "smart_contract_risk": {
                "code_coverage_threshold": 80,
                "formal_verification_required": False,
                "bug_bounty_required": True,
                "upgrade_timelock": 86400  # 24 hours
            },
            "operational_risk": {
                "team_doxx_required": False,
                "multisig_threshold": 3,
                "emergency_pause_enabled": True,
                "insurance_coverage": False
            },
            "monitoring": {
                "check_interval": 300,  # 5 minutes
                "alert_cooldown": 3600,  # 1 hour
                "max_alerts_per_hour": 10
            }
        }
        
        config_path = "backend/config/risk_config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                # Merge with defaults
                for key, value in loaded_config.items():
                    if key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        
        return default_config
    
    async def assess_protocol_risk(self, protocol: str) -> RiskAssessment:
        """Perform comprehensive risk assessment for a protocol"""
        
        logger.info(f"Assessing risk for protocol: {protocol}")
        
        try:
            # Collect risk metrics
            metrics = []
            
            # Market risk metrics
            market_metrics = await self._assess_market_risk(protocol)
            metrics.extend(market_metrics)
            
            # Liquidity risk metrics
            liquidity_metrics = await self._assess_liquidity_risk(protocol)
            metrics.extend(liquidity_metrics)
            
            # Smart contract risk metrics
            contract_metrics = await self._assess_smart_contract_risk(protocol)
            metrics.extend(contract_metrics)
            
            # Protocol risk metrics
            protocol_metrics = await self._assess_protocol_risk_metrics(protocol)
            metrics.extend(protocol_metrics)
            
            # Operational risk metrics
            operational_metrics = await self._assess_operational_risk(protocol)
            metrics.extend(operational_metrics)
            
            # Calculate overall risk score
            overall_score = self._calculate_overall_risk_score(metrics)
            overall_level = self._get_risk_level(overall_score)
            
            # Generate recommendations
            recommendations = self._generate_risk_recommendations(metrics, overall_level)
            
            # Create assessment
            assessment = RiskAssessment(
                protocol=protocol,
                overall_score=overall_score,
                overall_level=overall_level,
                metrics=metrics,
                recommendations=recommendations,
                timestamp=datetime.now()
            )
            
            # Store in history
            self.risk_history.append(assessment)
            
            # Check for alerts
            await self._check_risk_alerts(assessment)
            
            logger.info(f"Risk assessment completed for {protocol}: {overall_level.value} ({overall_score:.2f})")
            return assessment
            
        except Exception as e:
            logger.error(f"Risk assessment failed for {protocol}: {str(e)}")
            raise
    
    async def _assess_market_risk(self, protocol: str) -> List[RiskMetric]:
        """Assess market-related risks"""
        
        metrics = []
        
        try:
            # Get historical price data
            price_data = await self._get_price_data(protocol, days=30)
            
            if not price_data.empty:
                # Volatility
                returns = price_data['price'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(365)  # Annualized
                
                metrics.append(RiskMetric(
                    name="Price Volatility",
                    category=RiskCategory.MARKET,
                    value=volatility,
                    threshold=self.risk_config["market_risk"]["volatility_threshold"],
                    level=self._get_risk_level(volatility * 100),
                    description=f"Annualized price volatility: {volatility:.2%}",
                    timestamp=datetime.now()
                ))
                
                # Liquidity depth
                avg_liquidity = price_data['liquidity'].mean()
                liquidity_threshold = self.risk_config["market_risk"]["liquidity_threshold"]
                
                liquidity_score = min(100, (avg_liquidity / liquidity_threshold) * 100)
                
                metrics.append(RiskMetric(
                    name="Liquidity Depth",
                    category=RiskCategory.LIQUIDITY,
                    value=100 - liquidity_score,  # Invert so higher is riskier
                    threshold=50,
                    level=self._get_risk_level(100 - liquidity_score),
                    description=f"Average liquidity: ${avg_liquidity:,.0f}",
                    timestamp=datetime.now()
                ))
        
        except Exception as e:
            logger.error(f"Market risk assessment failed: {str(e)}")
        
        return metrics
    
    async def _assess_liquidity_risk(self, protocol: str) -> List[RiskMetric]:
        """Assess liquidity-related risks"""
        
        metrics = []
        
        try:
            # Get protocol liquidity data
            liquidity_data = await self._get_liquidity_data(protocol)
            
            # Utilization rate
            if 'utilization_rate' in liquidity_data:
                utilization = liquidity_data['utilization_rate']
                
                metrics.append(RiskMetric(
                    name="Utilization Rate",
                    category=RiskCategory.LIQUIDITY,
                    value=utilization * 100,
                    threshold=80,  # 80% utilization threshold
                    level=self._get_risk_level(utilization * 100),
                    description=f"Protocol utilization: {utilization:.1%}",
                    timestamp=datetime.now()
                ))
            
            # Withdrawal capacity
            if 'available_liquidity' in liquidity_data and 'total_deposits' in liquidity_data:
                withdrawal_capacity = liquidity_data['available_liquidity'] / liquidity_data['total_deposits']
                
                metrics.append(RiskMetric(
                    name="Withdrawal Capacity",
                    category=RiskCategory.LIQUIDITY,
                    value=(1 - withdrawal_capacity) * 100,  # Invert so lower capacity = higher risk
                    threshold=20,  # 20% minimum capacity
                    level=self._get_risk_level((1 - withdrawal_capacity) * 100),
                    description=f"Available for withdrawal: {withdrawal_capacity:.1%}",
                    timestamp=datetime.now()
                ))
        
        except Exception as e:
            logger.error(f"Liquidity risk assessment failed: {str(e)}")
        
        return metrics
    
    async def _assess_smart_contract_risk(self, protocol: str) -> List[RiskMetric]:
        """Assess smart contract risks"""
        
        metrics = []
        
        try:
            # Get contract information
            contract_info = await self._get_contract_info(protocol)
            
            # Contract age
            if 'deployment_date' in contract_info:
                age_days = (datetime.now() - contract_info['deployment_date']).days
                age_threshold = self.risk_config["protocol_risk"]["age_threshold"]
                
                age_score = min(100, (age_days / age_threshold) * 100)
                
                metrics.append(RiskMetric(
                    name="Contract Age",
                    category=RiskCategory.SMART_CONTRACT,
                    value=100 - age_score,  # Newer contracts are riskier
                    threshold=50,
                    level=self._get_risk_level(100 - age_score),
                    description=f"Contract deployed {age_days} days ago",
                    timestamp=datetime.now()
                ))
            
            # Audit status
            if 'audit_score' in contract_info:
                audit_score = contract_info['audit_score']
                
                metrics.append(RiskMetric(
                    name="Audit Score",
                    category=RiskCategory.SMART_CONTRACT,
                    value=100 - audit_score,  # Invert so lower audit score = higher risk
                    threshold=30,
                    level=self._get_risk_level(100 - audit_score),
                    description=f"Audit score: {audit_score}/100",
                    timestamp=datetime.now()
                ))
            
            # Upgrade mechanism
            if 'is_upgradeable' in contract_info:
                upgrade_risk = 50 if contract_info['is_upgradeable'] else 10
                
                metrics.append(RiskMetric(
                    name="Upgrade Risk",
                    category=RiskCategory.SMART_CONTRACT,
                    value=upgrade_risk,
                    threshold=30,
                    level=self._get_risk_level(upgrade_risk),
                    description="Contract is upgradeable" if contract_info['is_upgradeable'] else "Contract is immutable",
                    timestamp=datetime.now()
                ))
        
        except Exception as e:
            logger.error(f"Smart contract risk assessment failed: {str(e)}")
        
        return metrics
    
    async def _assess_protocol_risk_metrics(self, protocol: str) -> List[RiskMetric]:
        """Assess protocol-specific risks"""
        
        metrics = []
        
        try:
            # Get protocol data
            protocol_data = await self._get_protocol_data(protocol)
            
            # TVL risk
            if 'tvl' in protocol_data:
                tvl = protocol_data['tvl']
                tvl_threshold = self.risk_config["protocol_risk"]["tvl_threshold"]
                
                tvl_score = min(100, (tvl / tvl_threshold) * 100)
                
                metrics.append(RiskMetric(
                    name="TVL Risk",
                    category=RiskCategory.PROTOCOL,
                    value=100 - tvl_score,  # Lower TVL = higher risk
                    threshold=50,
                    level=self._get_risk_level(100 - tvl_score),
                    description=f"Total Value Locked: ${tvl:,.0f}",
                    timestamp=datetime.now()
                ))
            
            # Governance risk
            if 'governance_score' in protocol_data:
                governance_score = protocol_data['governance_score']
                
                metrics.append(RiskMetric(
                    name="Governance Risk",
                    category=RiskCategory.PROTOCOL,
                    value=100 - governance_score,
                    threshold=30,
                    level=self._get_risk_level(100 - governance_score),
                    description=f"Governance score: {governance_score}/100",
                    timestamp=datetime.now()
                ))
            
            # Concentration risk
            if 'top_depositor_share' in protocol_data:
                concentration = protocol_data['top_depositor_share'] * 100
                
                metrics.append(RiskMetric(
                    name="Concentration Risk",
                    category=RiskCategory.PROTOCOL,
                    value=concentration,
                    threshold=30,  # 30% concentration threshold
                    level=self._get_risk_level(concentration),
                    description=f"Top depositor holds {concentration:.1f}% of funds",
                    timestamp=datetime.now()
                ))
        
        except Exception as e:
            logger.error(f"Protocol risk assessment failed: {str(e)}")
        
        return metrics
    
    async def _assess_operational_risk(self, protocol: str) -> List[RiskMetric]:
        """Assess operational risks"""
        
        metrics = []
        
        try:
            # Get operational data
            operational_data = await self._get_operational_data(protocol)
            
            # Team risk
            if 'team_score' in operational_data:
                team_score = operational_data['team_score']
                
                metrics.append(RiskMetric(
                    name="Team Risk",
                    category=RiskCategory.OPERATIONAL,
                    value=100 - team_score,
                    threshold=30,
                    level=self._get_risk_level(100 - team_score),
                    description=f"Team credibility score: {team_score}/100",
                    timestamp=datetime.now()
                ))
            
            # Multisig risk
            if 'multisig_threshold' in operational_data:
                multisig_threshold = operational_data['multisig_threshold']
                required_threshold = self.risk_config["operational_risk"]["multisig_threshold"]
                
                multisig_risk = max(0, (required_threshold - multisig_threshold) * 20)
                
                metrics.append(RiskMetric(
                    name="Multisig Risk",
                    category=RiskCategory.OPERATIONAL,
                    value=multisig_risk,
                    threshold=40,
                    level=self._get_risk_level(multisig_risk),
                    description=f"Multisig threshold: {multisig_threshold}/{operational_data.get('multisig_total', 'N/A')}",
                    timestamp=datetime.now()
                ))
        
        except Exception as e:
            logger.error(f"Operational risk assessment failed: {str(e)}")
        
        return metrics
    
    def _calculate_overall_risk_score(self, metrics: List[RiskMetric]) -> float:
        """Calculate overall risk score from individual metrics"""
        
        if not metrics:
            return 50.0  # Default medium risk
        
        # Weight metrics by category
        category_weights = {
            RiskCategory.MARKET: 0.25,
            RiskCategory.LIQUIDITY: 0.20,
            RiskCategory.SMART_CONTRACT: 0.25,
            RiskCategory.PROTOCOL: 0.20,
            RiskCategory.OPERATIONAL: 0.10
        }
        
        category_scores = {}
        category_counts = {}
        
        # Group metrics by category
        for metric in metrics:
            if metric.category not in category_scores:
                category_scores[metric.category] = 0
                category_counts[metric.category] = 0
            
            category_scores[metric.category] += metric.value
            category_counts[metric.category] += 1
        
        # Calculate weighted average
        total_score = 0
        total_weight = 0
        
        for category, score in category_scores.items():
            if category_counts[category] > 0:
                avg_score = score / category_counts[category]
                weight = category_weights.get(category, 0.1)
                total_score += avg_score * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 50.0
    
    def _get_risk_level(self, score: float) -> RiskLevel:
        """Convert risk score to risk level"""
        
        if score < self.thresholds[RiskLevel.LOW]:
            return RiskLevel.LOW
        elif score < self.thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        elif score < self.thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _generate_risk_recommendations(self, 
                                     metrics: List[RiskMetric], 
                                     overall_level: RiskLevel) -> List[str]:
        """Generate risk mitigation recommendations"""
        
        recommendations = []
        
        # High-risk metrics
        high_risk_metrics = [m for m in metrics if m.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        
        for metric in high_risk_metrics:
            if metric.category == RiskCategory.LIQUIDITY:
                recommendations.append(f"Monitor {metric.name} closely - consider reducing allocation")
            elif metric.category == RiskCategory.SMART_CONTRACT:
                recommendations.append(f"Review {metric.name} - additional due diligence required")
            elif metric.category == RiskCategory.MARKET:
                recommendations.append(f"High {metric.name} detected - implement stop-loss mechanisms")
            elif metric.category == RiskCategory.PROTOCOL:
                recommendations.append(f"{metric.name} concern - diversify across protocols")
        
        # Overall level recommendations
        if overall_level == RiskLevel.CRITICAL:
            recommendations.append("CRITICAL RISK: Consider immediate position reduction or exit")
        elif overall_level == RiskLevel.HIGH:
            recommendations.append("HIGH RISK: Reduce position size and increase monitoring frequency")
        elif overall_level == RiskLevel.MEDIUM:
            recommendations.append("MEDIUM RISK: Maintain current allocation with regular monitoring")
        
        return recommendations
    
    async def _check_risk_alerts(self, assessment: RiskAssessment):
        """Check for risk alerts and create notifications"""
        
        for metric in assessment.metrics:
            if metric.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                alert_id = f"{assessment.protocol}_{metric.name}_{int(datetime.now().timestamp())}"
                
                alert = RiskAlert(
                    id=alert_id,
                    protocol=assessment.protocol,
                    category=metric.category,
                    level=metric.level,
                    message=f"{metric.name} exceeded threshold: {metric.value:.2f} > {metric.threshold}",
                    metric_value=metric.value,
                    threshold=metric.threshold,
                    timestamp=datetime.now()
                )
                
                self.active_alerts[alert_id] = alert
                logger.warning(f"Risk alert created: {alert.message}")
    
    # Placeholder methods for data collection (would integrate with actual data sources)
    async def _get_price_data(self, protocol: str, days: int) -> pd.DataFrame:
        """Get historical price data"""
        # Placeholder - would integrate with price feeds
        return pd.DataFrame()
    
    async def _get_liquidity_data(self, protocol: str) -> Dict[str, Any]:
        """Get liquidity data"""
        # Placeholder - would integrate with protocol APIs
        return {}
    
    async def _get_contract_info(self, protocol: str) -> Dict[str, Any]:
        """Get smart contract information"""
        # Placeholder - would integrate with contract analysis tools
        return {}
    
    async def _get_protocol_data(self, protocol: str) -> Dict[str, Any]:
        """Get protocol data"""
        # Placeholder - would integrate with DeFi data providers
        return {}
    
    async def _get_operational_data(self, protocol: str) -> Dict[str, Any]:
        """Get operational data"""
        # Placeholder - would integrate with governance and team data
        return {}
    
    async def start_monitoring(self):
        """Start continuous risk monitoring"""
        
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        logger.info("Starting risk monitoring...")
        
        while self.monitoring_active:
            try:
                # Monitor all protocols
                protocols = await self._get_monitored_protocols()
                
                for protocol in protocols:
                    assessment = await self.assess_protocol_risk(protocol)
                    
                    # Check for circuit breaker conditions
                    if assessment.overall_level == RiskLevel.CRITICAL:
                        await self._trigger_circuit_breaker(protocol, assessment)
                
                # Wait for next check
                await asyncio.sleep(self.risk_config["monitoring"]["check_interval"])
                
            except Exception as e:
                logger.error(f"Error in risk monitoring: {str(e)}")
                await asyncio.sleep(60)
    
    async def stop_monitoring(self):
        """Stop risk monitoring"""
        self.monitoring_active = False
        logger.info("Risk monitoring stopped")
    
    async def _get_monitored_protocols(self) -> List[str]:
        """Get list of protocols to monitor"""
        # Placeholder - would get from configuration or active vaults
        return ["compound", "aave", "yearn"]
    
    async def _trigger_circuit_breaker(self, protocol: str, assessment: RiskAssessment):
        """Trigger circuit breaker for critical risk"""
        
        logger.critical(f"CIRCUIT BREAKER TRIGGERED for {protocol}: {assessment.overall_score:.2f}")
        
        # Would integrate with vault contracts to pause operations
        # For now, just log the event
        
        # Create critical alert
        alert = RiskAlert(
            id=f"circuit_breaker_{protocol}_{int(datetime.now().timestamp())}",
            protocol=protocol,
            category=RiskCategory.OPERATIONAL,
            level=RiskLevel.CRITICAL,
            message=f"Circuit breaker triggered for {protocol} due to critical risk level",
            metric_value=assessment.overall_score,
            threshold=self.thresholds[RiskLevel.CRITICAL],
            timestamp=datetime.now()
        )
        
        self.active_alerts[alert.id] = alert
    
    def get_active_alerts(self) -> List[RiskAlert]:
        """Get all active risk alerts"""
        return list(self.active_alerts.values())
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge a risk alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            logger.info(f"Alert {alert_id} acknowledged")
    
    def get_risk_history(self, protocol: str = None, days: int = 30) -> List[RiskAssessment]:
        """Get risk assessment history"""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        history = [
            assessment for assessment in self.risk_history
            if assessment.timestamp >= cutoff_date
        ]
        
        if protocol:
            history = [a for a in history if a.protocol == protocol]
        
        return history
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get risk monitoring summary"""
        
        active_alerts_by_level = {}
        for alert in self.active_alerts.values():
            level = alert.level.value
            if level not in active_alerts_by_level:
                active_alerts_by_level[level] = 0
            active_alerts_by_level[level] += 1
        
        return {
            'monitoring_active': self.monitoring_active,
            'total_assessments': len(self.risk_history),
            'active_alerts': len(self.active_alerts),
            'alerts_by_level': active_alerts_by_level,
            'last_assessment': (
                max(self.risk_history, key=lambda x: x.timestamp).timestamp.isoformat()
                if self.risk_history else None
            )
        }
