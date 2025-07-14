# AI-Driven Yield Farming API Documentation

## Overview

The AI-Driven Yield Farming API provides comprehensive endpoints for managing yield farming vaults, AI-powered strategy optimization, risk assessment, and automation. This RESTful API is built with FastAPI and provides real-time data through WebSocket connections.

## Base URL

- **Production**: `https://api.yieldfarm.ai`
- **Staging**: `https://staging-api.yieldfarm.ai`
- **Development**: `http://localhost:8000`

## Authentication

The API uses JWT (JSON Web Tokens) for authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Getting a Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "wallet_address": "0x...",
  "signature": "0x...",
  "message": "Login message"
}
```

## Rate Limiting

- **Standard endpoints**: 100 requests per minute
- **ML prediction endpoints**: 10 requests per minute
- **WebSocket connections**: 5 concurrent connections per user

## API Endpoints

### System Endpoints

#### Health Check
```http
GET /health
```

Returns system health status and service availability.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "web3": {"status": "healthy", "connected": true},
    "ml": {"status": "healthy", "models": {...}},
    "database": {"status": "healthy"}
  }
}
```

#### System Information
```http
GET /api/v1/system/info
```

Returns API version and supported features.

### Vault Management

#### List All Vaults
```http
GET /api/v1/vaults
```

**Query Parameters:**
- `risk_profile` (optional): Filter by risk profile (conservative, moderate, aggressive)
- `status` (optional): Filter by status (active, paused, deprecated)
- `min_apy` (optional): Minimum APY filter
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset

**Response:**
```json
[
  {
    "id": "0x123...",
    "name": "Conservative USDC Vault",
    "symbol": "cvUSDC",
    "asset": "0x456...",
    "total_assets": 1000000,
    "total_supply": 1000000,
    "apy": 8.5,
    "risk_profile": "conservative",
    "risk_score": 25,
    "status": "active",
    "strategies": ["0x789..."],
    "created_at": "2024-01-01T00:00:00Z",
    "last_rebalance": "2024-01-15T08:00:00Z"
  }
]
```

#### Get Vault Details
```http
GET /api/v1/vaults/{vault_id}
```

**Response:**
```json
{
  "id": "0x123...",
  "name": "Conservative USDC Vault",
  "symbol": "cvUSDC",
  "asset": "0x456...",
  "total_assets": 1000000,
  "total_supply": 1000000,
  "apy": 8.5,
  "risk_profile": "conservative",
  "risk_score": 25,
  "status": "active",
  "strategies": [
    {
      "address": "0x789...",
      "name": "Compound USDC Strategy",
      "allocation": 0.6,
      "apy": 7.2,
      "risk_score": 20
    }
  ],
  "performance_metrics": {
    "total_return": 12.5,
    "sharpe_ratio": 1.8,
    "max_drawdown": 2.1,
    "volatility": 5.2
  },
  "fees": {
    "management_fee": 0.02,
    "performance_fee": 0.15
  }
}
```

#### Create New Vault
```http
POST /api/v1/vaults
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "My Custom Vault",
  "symbol": "MCV",
  "asset": "0x456...",
  "risk_profile": "moderate",
  "initial_strategies": [
    {
      "strategy": "0x789...",
      "allocation": 0.5
    }
  ]
}
```

**Response:**
```json
{
  "id": "0x123...",
  "transaction_hash": "0xabc...",
  "status": "pending",
  "estimated_confirmation": "2024-01-15T10:35:00Z"
}
```

#### Deposit to Vault
```http
POST /api/v1/vaults/{vault_id}/deposit
Content-Type: application/json
Authorization: Bearer <token>

{
  "amount": "1000.0",
  "recipient": "0x..."
}
```

#### Withdraw from Vault
```http
POST /api/v1/vaults/{vault_id}/withdraw
Content-Type: application/json
Authorization: Bearer <token>

{
  "amount": "500.0",
  "recipient": "0x..."
}
```

### AI/ML Endpoints

#### Predict Yields
```http
POST /api/v1/analytics/predict-yields
Content-Type: application/json
Authorization: Bearer <token>

{
  "protocols": ["compound", "aave", "yearn"],
  "horizon_days": 7,
  "confidence_threshold": 0.8
}
```

**Response:**
```json
[
  {
    "protocol": "compound",
    "predicted_apy": 8.5,
    "confidence": 0.85,
    "prediction_horizon": 7,
    "risk_score": 25.0,
    "timestamp": "2024-01-15T10:30:00Z"
  }
]
```

#### Get Strategy Recommendation
```http
POST /api/v1/analytics/recommend-strategy
Content-Type: application/json
Authorization: Bearer <token>

{
  "risk_profile": "moderate",
  "investment_amount": 10000,
  "protocols": ["compound", "aave", "yearn"],
  "constraints": {
    "max_protocol_allocation": 0.5,
    "min_diversification": 3
  }
}
```

**Response:**
```json
{
  "allocations": {
    "compound": 0.4,
    "aave": 0.35,
    "yearn": 0.25
  },
  "expected_apy": 9.2,
  "risk_score": 35.0,
  "confidence": 0.78,
  "rebalance_frequency": 24,
  "reasoning": [
    "Compound offers stable yields with low risk",
    "Aave provides good diversification",
    "Yearn adds higher yield potential"
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Model Status
```http
GET /api/v1/analytics/models/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "yield_predictor": {
    "status": "active",
    "accuracy": 0.85,
    "last_trained": "2024-01-14T02:00:00Z",
    "next_training": "2024-01-15T02:00:00Z"
  },
  "strategy_selector": {
    "status": "active",
    "accuracy": 0.78,
    "last_trained": "2024-01-14T02:00:00Z"
  }
}
```

### Risk Management

#### Assess Protocol Risk
```http
GET /api/v1/risk/assess/{protocol}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "protocol": "compound",
  "overall_score": 25.0,
  "overall_level": "low",
  "metrics": [
    {
      "name": "Price Volatility",
      "category": "market",
      "value": 15.2,
      "threshold": 30.0,
      "level": "low"
    }
  ],
  "recommendations": [
    "Monitor liquidity closely",
    "Consider position size limits"
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Get Risk Alerts
```http
GET /api/v1/risk/alerts
Authorization: Bearer <token>
```

**Query Parameters:**
- `level` (optional): Filter by risk level
- `protocol` (optional): Filter by protocol
- `acknowledged` (optional): Filter by acknowledgment status

### User Management

#### Get User Portfolio
```http
GET /api/v1/users/{address}/portfolio
Authorization: Bearer <token>
```

**Response:**
```json
{
  "total_value": 50000,
  "total_return": 2500,
  "allocations": [
    {
      "protocol": "compound",
      "value": 20000,
      "allocation": 0.4,
      "apy": 8.5,
      "risk_score": 25
    }
  ],
  "performance": {
    "daily_return": 0.02,
    "weekly_return": 0.15,
    "monthly_return": 0.85
  }
}
```

#### Get User Summary
```http
GET /api/v1/users/{address}/summary
Authorization: Bearer <token>
```

### Automation

#### Get Automation Status
```http
GET /api/v1/automation/status
Authorization: Bearer <token>
```

#### Trigger Manual Rebalance
```http
POST /api/v1/automation/rebalance/{vault_id}
Authorization: Bearer <token>
```

## WebSocket Endpoints

### Real-time Vault Updates
```
ws://localhost:8000/ws/vault/{vault_id}
```

**Message Format:**
```json
{
  "type": "vault_update",
  "data": {
    "vault_id": "0x123...",
    "total_assets": 1000000,
    "apy": 8.5,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Real-time Portfolio Updates
```
ws://localhost:8000/ws/portfolio/{address}
```

## Error Handling

The API uses standard HTTP status codes and returns detailed error information:

```json
{
  "error": {
    "code": 400,
    "message": "Invalid request parameters",
    "details": {
      "field": "amount",
      "issue": "Must be greater than 0"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Error Codes

- `400` - Bad Request: Invalid parameters
- `401` - Unauthorized: Invalid or missing token
- `403` - Forbidden: Insufficient permissions
- `404` - Not Found: Resource not found
- `429` - Too Many Requests: Rate limit exceeded
- `500` - Internal Server Error: Server error
- `503` - Service Unavailable: Service temporarily unavailable

## SDK Examples

### Python SDK
```python
from yield_farming_sdk import YieldFarmingClient

client = YieldFarmingClient(
    api_url="https://api.yieldfarm.ai",
    api_key="your-api-key"
)

# Get vault information
vault = client.vaults.get("0x123...")

# Get yield predictions
predictions = client.analytics.predict_yields(
    protocols=["compound", "aave"],
    horizon_days=7
)

# Create new vault
vault = client.vaults.create(
    name="My Vault",
    asset="0x456...",
    risk_profile="moderate"
)
```

### JavaScript SDK
```javascript
import { YieldFarmingClient } from '@yieldfarm/sdk';

const client = new YieldFarmingClient({
  apiUrl: 'https://api.yieldfarm.ai',
  apiKey: 'your-api-key'
});

// Get strategy recommendation
const recommendation = await client.analytics.recommendStrategy({
  riskProfile: 'moderate',
  investmentAmount: 10000,
  protocols: ['compound', 'aave', 'yearn']
});

// Subscribe to real-time updates
client.websocket.subscribe('vault', vaultId, (data) => {
  console.log('Vault update:', data);
});
```

## Changelog

### v1.0.0 (2024-01-15)
- Initial API release
- Vault management endpoints
- AI/ML prediction endpoints
- Risk assessment endpoints
- WebSocket support

## Support

For API support, please contact:
- Email: api-support@yieldfarm.ai
- Discord: https://discord.gg/yieldfarm
- Documentation: https://docs.yieldfarm.ai
