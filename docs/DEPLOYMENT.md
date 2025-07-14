# Deployment Guide

This guide covers deploying the AI-Driven Yield Farming platform to production environments.

## Prerequisites

### Infrastructure Requirements

- **Kubernetes Cluster**: v1.25+ with at least 3 nodes
- **Node Specifications**: 
  - 4 vCPUs, 16GB RAM minimum per node
  - 100GB SSD storage per node
- **Load Balancer**: For ingress traffic
- **SSL Certificates**: For HTTPS termination
- **Container Registry**: For storing Docker images

### External Services

- **Blockchain RPC**: Infura, Alchemy, or self-hosted node
- **Database**: PostgreSQL 15+ (managed service recommended)
- **Cache**: Redis 7+ (managed service recommended)
- **Monitoring**: Prometheus + Grafana stack
- **Logging**: ELK stack or managed logging service

### Required Secrets

```bash
# Blockchain
INFURA_API_KEY=your_infura_key
PRIVATE_KEY=your_private_key
CHAINLINK_REGISTRY_ADDRESS=0x...
GELATO_RELAY_API_KEY=your_gelato_key

# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://user:pass@host:6379

# Security
JWT_SECRET=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key

# External APIs
COINGECKO_API_KEY=your_coingecko_key
DUNE_API_KEY=your_dune_key

# Monitoring
GRAFANA_PASSWORD=your_grafana_password
SLACK_WEBHOOK=your_slack_webhook
```

## Deployment Methods

### Method 1: Docker Compose (Development/Staging)

1. **Clone the repository**:
```bash
git clone https://github.com/your-org/ai-yield-farming.git
cd ai-yield-farming
```

2. **Set environment variables**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Deploy with Docker Compose**:
```bash
# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker-compose ps
docker-compose logs -f
```

4. **Initialize the database**:
```bash
docker-compose exec backend python scripts/init_db.py
```

5. **Train initial ML models**:
```bash
docker-compose exec ml-trainer python training/train_models.py
```

### Method 2: Kubernetes (Production)

1. **Prepare the cluster**:
```bash
# Create namespace
kubectl create namespace yield-farming

# Create secrets
kubectl create secret generic yield-farming-secrets \
  --from-literal=database-url="$DATABASE_URL" \
  --from-literal=redis-url="$REDIS_URL" \
  --from-literal=infura-api-key="$INFURA_API_KEY" \
  --from-literal=private-key="$PRIVATE_KEY" \
  --from-literal=jwt-secret="$JWT_SECRET" \
  -n yield-farming

# Create config map
kubectl create configmap yield-farming-config \
  --from-literal=chainlink-registry-address="$CHAINLINK_REGISTRY_ADDRESS" \
  --from-literal=environment="production" \
  -n yield-farming
```

2. **Deploy infrastructure components**:
```bash
# Deploy PostgreSQL (if not using managed service)
kubectl apply -f k8s/infrastructure/postgres.yaml

# Deploy Redis (if not using managed service)
kubectl apply -f k8s/infrastructure/redis.yaml

# Deploy monitoring stack
kubectl apply -f k8s/monitoring/
```

3. **Deploy application components**:
```bash
# Deploy backend
kubectl apply -f k8s/production/backend-deployment.yaml

# Deploy ML trainer
kubectl apply -f k8s/production/ml-trainer-deployment.yaml

# Deploy automation service
kubectl apply -f k8s/production/automation-deployment.yaml

# Deploy frontend
kubectl apply -f k8s/production/frontend-deployment.yaml

# Deploy ingress
kubectl apply -f k8s/production/ingress.yaml
```

4. **Verify deployment**:
```bash
# Check pod status
kubectl get pods -n yield-farming

# Check services
kubectl get services -n yield-farming

# Check ingress
kubectl get ingress -n yield-farming

# View logs
kubectl logs -f deployment/yield-farming-backend -n yield-farming
```

### Method 3: Helm Chart (Recommended for Production)

1. **Install Helm chart**:
```bash
# Add repository
helm repo add yield-farming https://charts.yieldfarm.ai
helm repo update

# Install with custom values
helm install yield-farming yield-farming/ai-yield-farming \
  --namespace yield-farming \
  --create-namespace \
  --values values.production.yaml
```

2. **Custom values file** (`values.production.yaml`):
```yaml
global:
  environment: production
  imageRegistry: ghcr.io/your-org
  imageTag: "v1.0.0"

backend:
  replicaCount: 3
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10

database:
  external: true
  host: "your-postgres-host"
  port: 5432
  database: "yield_farming"

redis:
  external: true
  host: "your-redis-host"
  port: 6379

ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: api.yieldfarm.ai
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: yieldfarm-tls
      hosts:
        - api.yieldfarm.ai

monitoring:
  prometheus:
    enabled: true
  grafana:
    enabled: true
    adminPassword: "your-secure-password"
```

## Smart Contract Deployment

### 1. Compile Contracts
```bash
npx hardhat compile
```

### 2. Deploy to Testnet
```bash
# Deploy to Goerli testnet
npx hardhat run scripts/deploy.js --network goerli

# Verify contracts
npx hardhat verify --network goerli DEPLOYED_CONTRACT_ADDRESS
```

### 3. Deploy to Mainnet
```bash
# Deploy to Ethereum mainnet
npx hardhat run scripts/deploy.js --network mainnet

# Verify contracts
npx hardhat verify --network mainnet DEPLOYED_CONTRACT_ADDRESS
```

### 4. Update Configuration
```bash
# Update contract addresses in configuration
kubectl patch configmap yield-farming-config \
  --patch '{"data":{"vault-factory-address":"0x..."}}' \
  -n yield-farming
```

## Database Migration

### Initial Setup
```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Or in Kubernetes
kubectl exec -it deployment/yield-farming-backend -n yield-farming -- \
  alembic upgrade head
```

### Schema Updates
```bash
# Create new migration
alembic revision --autogenerate -m "Add new table"

# Apply migration
alembic upgrade head
```

## SSL/TLS Configuration

### Using Let's Encrypt with cert-manager
```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yieldfarm.ai
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

## Monitoring Setup

### Prometheus Configuration
```bash
# Deploy Prometheus
kubectl apply -f k8s/monitoring/prometheus/

# Access Prometheus UI
kubectl port-forward svc/prometheus 9090:9090 -n monitoring
```

### Grafana Dashboards
```bash
# Import dashboards
kubectl apply -f k8s/monitoring/grafana/dashboards/

# Access Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring
```

### Alerting
```bash
# Configure Alertmanager
kubectl apply -f k8s/monitoring/alertmanager/

# Test alerts
curl -X POST http://localhost:9093/api/v1/alerts
```

## Backup and Recovery

### Database Backup
```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

pg_dump $DATABASE_URL > $BACKUP_DIR/database.sql
aws s3 cp $BACKUP_DIR/database.sql s3://your-backup-bucket/
```

### ML Model Backup
```bash
# Backup trained models
kubectl exec deployment/yield-farming-ml-trainer -n yield-farming -- \
  tar -czf /tmp/models.tar.gz /app/models/

kubectl cp yield-farming/yield-farming-ml-trainer-xxx:/tmp/models.tar.gz ./models-backup.tar.gz
```

## Security Hardening

### Network Policies
```bash
# Apply network policies
kubectl apply -f k8s/security/network-policies/
```

### Pod Security Standards
```bash
# Enable pod security standards
kubectl label namespace yield-farming \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

### Secret Management
```bash
# Use external secret management
kubectl apply -f k8s/security/external-secrets/
```

## Performance Optimization

### Resource Limits
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### Horizontal Pod Autoscaling
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: yield-farming-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Troubleshooting

### Common Issues

1. **Pod CrashLoopBackOff**:
```bash
kubectl describe pod <pod-name> -n yield-farming
kubectl logs <pod-name> -n yield-farming --previous
```

2. **Database Connection Issues**:
```bash
kubectl exec -it deployment/yield-farming-backend -n yield-farming -- \
  python -c "import psycopg2; print('DB connection OK')"
```

3. **ML Model Loading Issues**:
```bash
kubectl exec -it deployment/yield-farming-ml-trainer -n yield-farming -- \
  python -c "from ml.models.yield_predictor import YieldPredictor; print('Models OK')"
```

### Health Checks
```bash
# API health
curl https://api.yieldfarm.ai/health

# Database health
kubectl exec deployment/yield-farming-backend -n yield-farming -- \
  python scripts/health_check.py

# ML service health
kubectl exec deployment/yield-farming-ml-trainer -n yield-farming -- \
  python scripts/model_health_check.py
```

## Rollback Procedures

### Application Rollback
```bash
# Rollback to previous version
kubectl rollout undo deployment/yield-farming-backend -n yield-farming

# Rollback to specific revision
kubectl rollout undo deployment/yield-farming-backend --to-revision=2 -n yield-farming
```

### Database Rollback
```bash
# Rollback database migration
alembic downgrade -1

# Restore from backup
psql $DATABASE_URL < backup.sql
```

## Maintenance

### Regular Tasks
- Monitor system health and performance
- Update dependencies and security patches
- Backup databases and ML models
- Review and rotate secrets
- Update SSL certificates
- Monitor blockchain network upgrades

### Scheduled Maintenance
- Weekly: Security updates
- Monthly: Dependency updates
- Quarterly: Full system review and optimization
