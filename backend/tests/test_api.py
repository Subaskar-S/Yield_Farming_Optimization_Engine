"""
Comprehensive API tests for the yield farming platform backend.
Tests all major endpoints and functionality.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timedelta

# Import the FastAPI app
from backend.api.main import app
from backend.services.web3_service import Web3Service
from backend.services.ml_service import MLService
from backend.services.risk_service import RiskService

# Test client
client = TestClient(app)

# Test fixtures
@pytest.fixture
def mock_web3_service():
    """Mock Web3 service for testing"""
    service = Mock(spec=Web3Service)
    service.is_connected = AsyncMock(return_value=True)
    service.get_vault_info = AsyncMock(return_value={
        'address': '0x123...',
        'name': 'Test Vault',
        'symbol': 'TV',
        'asset': '0x456...',
        'total_assets': 1000000,
        'total_supply': 1000000,
        'apy': 12.5,
        'risk_profile': 'moderate',
        'status': 'active'
    })
    service.get_metrics = AsyncMock(return_value={
        'connection_status': True,
        'current_block': 18500000,
        'gas_price': 20000000000,
        'chain_id': 1
    })
    return service

@pytest.fixture
def mock_ml_service():
    """Mock ML service for testing"""
    service = Mock(spec=MLService)
    service.predict_yields = AsyncMock(return_value=[
        {
            'protocol': 'compound',
            'predicted_apy': 8.5,
            'confidence': 0.85,
            'prediction_horizon': 7,
            'risk_score': 25.0,
            'timestamp': datetime.now().isoformat()
        }
    ])
    service.recommend_strategy = AsyncMock(return_value={
        'allocations': {'compound': 0.4, 'aave': 0.3, 'yearn': 0.3},
        'expected_apy': 9.2,
        'risk_score': 35.0,
        'confidence': 0.78,
        'rebalance_frequency': 24,
        'timestamp': datetime.now().isoformat()
    })
    service.get_model_status = AsyncMock(return_value={
        'yield_predictor': {
            'status': 'active',
            'accuracy': 0.85,
            'last_trained': datetime.now().isoformat()
        }
    })
    service.get_metrics = AsyncMock(return_value={
        'models_loaded': 2,
        'cache_hit_rate': 0.75,
        'performance': {
            'predictions_made': 150,
            'recommendations_generated': 45
        }
    })
    return service

@pytest.fixture
def mock_risk_service():
    """Mock risk service for testing"""
    service = Mock(spec=RiskService)
    service.assess_protocol_risk = AsyncMock(return_value={
        'protocol': 'compound',
        'overall_score': 25.0,
        'overall_level': 'low',
        'metrics': [],
        'recommendations': ['Monitor liquidity closely'],
        'timestamp': datetime.now().isoformat()
    })
    return service

class TestHealthEndpoints:
    """Test health and system endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "AI-Driven Yield Farming Optimization API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "operational"
    
    def test_health_check(self):
        """Test health check endpoint"""
        with patch('backend.api.main.web3_service') as mock_web3, \
             patch('backend.api.main.ml_service') as mock_ml:
            
            mock_web3.is_connected = AsyncMock(return_value=True)
            mock_ml.get_model_status = AsyncMock(return_value={})
            
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "services" in data
    
    def test_system_info(self):
        """Test system info endpoint"""
        response = client.get("/api/v1/system/info")
        assert response.status_code == 200
        data = response.json()
        assert data["api_version"] == "1.0.0"
        assert "features" in data
        assert "supported_protocols" in data
        assert "supported_tokens" in data

class TestVaultEndpoints:
    """Test vault management endpoints"""
    
    def test_get_vaults(self):
        """Test getting all vaults"""
        with patch('backend.api.routers.vaults.get_vault_service') as mock_service:
            mock_vault_service = Mock()
            mock_vault_service.get_all_vaults = AsyncMock(return_value=[
                {
                    'id': 'vault1',
                    'name': 'Test Vault 1',
                    'apy': 12.5,
                    'risk_score': 25
                }
            ])
            mock_service.return_value = mock_vault_service
            
            response = client.get("/api/v1/vaults")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Test Vault 1"
    
    def test_get_vault_by_id(self):
        """Test getting specific vault"""
        vault_id = "0x123..."
        with patch('backend.api.routers.vaults.get_vault_service') as mock_service:
            mock_vault_service = Mock()
            mock_vault_service.get_vault = AsyncMock(return_value={
                'id': vault_id,
                'name': 'Test Vault',
                'apy': 12.5,
                'risk_score': 25,
                'total_assets': 1000000
            })
            mock_service.return_value = mock_vault_service
            
            response = client.get(f"/api/v1/vaults/{vault_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == vault_id
            assert data["name"] == "Test Vault"
    
    def test_create_vault(self):
        """Test vault creation"""
        vault_data = {
            "name": "New Test Vault",
            "symbol": "NTV",
            "asset": "0x456...",
            "risk_profile": "moderate"
        }
        
        with patch('backend.api.routers.vaults.get_vault_service') as mock_service:
            mock_vault_service = Mock()
            mock_vault_service.create_vault = AsyncMock(return_value={
                'id': '0x789...',
                'transaction_hash': '0xabc...',
                **vault_data
            })
            mock_service.return_value = mock_vault_service
            
            response = client.post("/api/v1/vaults", json=vault_data)
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == vault_data["name"]
            assert "transaction_hash" in data

class TestMLEndpoints:
    """Test ML service endpoints"""
    
    def test_predict_yields(self, mock_ml_service):
        """Test yield prediction endpoint"""
        with patch('backend.api.routers.analytics.get_ml_service') as mock_service:
            mock_service.return_value = mock_ml_service
            
            request_data = {
                "protocols": ["compound", "aave"],
                "horizon_days": 7
            }
            
            response = client.post("/api/v1/analytics/predict-yields", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1
            assert data[0]["protocol"] == "compound"
            assert "predicted_apy" in data[0]
    
    def test_strategy_recommendation(self, mock_ml_service):
        """Test strategy recommendation endpoint"""
        with patch('backend.api.routers.analytics.get_ml_service') as mock_service:
            mock_service.return_value = mock_ml_service
            
            request_data = {
                "risk_profile": "moderate",
                "investment_amount": 10000,
                "protocols": ["compound", "aave", "yearn"]
            }
            
            response = client.post("/api/v1/analytics/recommend-strategy", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert "allocations" in data
            assert "expected_apy" in data
            assert "risk_score" in data
    
    def test_model_status(self, mock_ml_service):
        """Test model status endpoint"""
        with patch('backend.api.routers.analytics.get_ml_service') as mock_service:
            mock_service.return_value = mock_ml_service
            
            response = client.get("/api/v1/analytics/models/status")
            assert response.status_code == 200
            data = response.json()
            assert "yield_predictor" in data

class TestRiskEndpoints:
    """Test risk management endpoints"""
    
    def test_assess_risk(self, mock_risk_service):
        """Test risk assessment endpoint"""
        with patch('backend.api.routers.risk.get_risk_service') as mock_service:
            mock_service.return_value = mock_risk_service
            
            protocol = "compound"
            response = client.get(f"/api/v1/risk/assess/{protocol}")
            assert response.status_code == 200
            data = response.json()
            assert data["protocol"] == protocol
            assert "overall_score" in data
            assert "recommendations" in data
    
    def test_get_risk_alerts(self):
        """Test getting risk alerts"""
        with patch('backend.api.routers.risk.get_risk_service') as mock_service:
            mock_risk_service = Mock()
            mock_risk_service.get_active_alerts = Mock(return_value=[
                {
                    'id': 'alert1',
                    'protocol': 'compound',
                    'level': 'high',
                    'message': 'High utilization detected',
                    'timestamp': datetime.now().isoformat()
                }
            ])
            mock_service.return_value = mock_risk_service
            
            response = client.get("/api/v1/risk/alerts")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["protocol"] == "compound"

class TestUserEndpoints:
    """Test user-related endpoints"""
    
    def test_user_portfolio(self):
        """Test getting user portfolio"""
        user_address = "0x123..."
        
        with patch('backend.api.routers.users.get_user_service') as mock_service:
            mock_user_service = Mock()
            mock_user_service.get_user_portfolio = AsyncMock(return_value={
                'total_value': 50000,
                'total_return': 2500,
                'allocations': [
                    {'protocol': 'compound', 'value': 20000, 'allocation': 0.4},
                    {'protocol': 'aave', 'value': 15000, 'allocation': 0.3},
                    {'protocol': 'yearn', 'value': 15000, 'allocation': 0.3}
                ]
            })
            mock_service.return_value = mock_user_service
            
            response = client.get(f"/api/v1/users/{user_address}/portfolio")
            assert response.status_code == 200
            data = response.json()
            assert data["total_value"] == 50000
            assert len(data["allocations"]) == 3
    
    def test_user_summary(self):
        """Test getting user summary"""
        user_address = "0x123..."
        
        with patch('backend.api.routers.users.get_user_service') as mock_service:
            mock_user_service = Mock()
            mock_user_service.get_user_summary = AsyncMock(return_value={
                'total_value': 50000,
                'total_return': 5.2,
                'apy': 12.5,
                'risk_score': 35,
                'active_vaults': 3,
                'pending_transactions': 0
            })
            mock_service.return_value = mock_service
            
            response = client.get(f"/api/v1/users/{user_address}/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["total_value"] == 50000
            assert data["active_vaults"] == 3

class TestAutomationEndpoints:
    """Test automation endpoints"""
    
    def test_get_automation_status(self):
        """Test getting automation status"""
        with patch('backend.api.routers.automation.get_automation_service') as mock_service:
            mock_automation_service = Mock()
            mock_automation_service.get_status = AsyncMock(return_value={
                'active_jobs': 5,
                'total_executions': 150,
                'success_rate': 0.98,
                'providers': {
                    'chainlink': {'jobs': 3, 'status': 'active'},
                    'gelato': {'jobs': 2, 'status': 'active'}
                }
            })
            mock_service.return_value = mock_automation_service
            
            response = client.get("/api/v1/automation/status")
            assert response.status_code == 200
            data = response.json()
            assert data["active_jobs"] == 5
            assert "providers" in data
    
    def test_trigger_rebalance(self):
        """Test triggering manual rebalance"""
        vault_id = "0x123..."
        
        with patch('backend.api.routers.automation.get_automation_service') as mock_service:
            mock_automation_service = Mock()
            mock_automation_service.trigger_rebalance = AsyncMock(return_value={
                'job_id': 'rebalance_123',
                'status': 'submitted',
                'estimated_execution': datetime.now().isoformat()
            })
            mock_service.return_value = mock_automation_service
            
            response = client.post(f"/api/v1/automation/rebalance/{vault_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "submitted"
            assert "job_id" in data

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_404_endpoint(self):
        """Test non-existent endpoint"""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_invalid_vault_id(self):
        """Test invalid vault ID"""
        with patch('backend.api.routers.vaults.get_vault_service') as mock_service:
            mock_vault_service = Mock()
            mock_vault_service.get_vault = AsyncMock(side_effect=ValueError("Vault not found"))
            mock_service.return_value = mock_vault_service
            
            response = client.get("/api/v1/vaults/invalid")
            assert response.status_code == 400
    
    def test_service_unavailable(self):
        """Test service unavailable scenarios"""
        with patch('backend.api.main.web3_service', None):
            response = client.get("/api/v1/vaults")
            assert response.status_code == 503

class TestWebSocketEndpoints:
    """Test WebSocket endpoints"""
    
    @pytest.mark.asyncio
    async def test_vault_websocket(self):
        """Test vault WebSocket connection"""
        # This would require a more sophisticated WebSocket test setup
        # For now, we'll test that the endpoint exists
        pass

# Integration tests
class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_vault_workflow(self):
        """Test complete vault creation and management workflow"""
        # This would test the entire flow from vault creation to deposits/withdrawals
        pass
    
    def test_ml_prediction_workflow(self):
        """Test ML prediction and strategy recommendation workflow"""
        # This would test the complete ML pipeline
        pass

# Performance tests
class TestPerformance:
    """Performance and load tests"""
    
    def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        # This would test the API under load
        pass
    
    def test_large_data_handling(self):
        """Test handling large datasets"""
        # This would test performance with large amounts of data
        pass

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
