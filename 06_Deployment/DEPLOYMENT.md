# DEPLOYMENT.md — Deployment Guide

## Overview

| Environment | URL | Purpose |
|-------------|-----|---------|
| Development | http://localhost:8000 | Local dev with hot reload |
| Staging | https://staging.justice-ai.com | Pre-production validation |
| Production | https://api.justice-ai.com | Live traffic |

---

## Infrastructure Requirements

### Minimum Specs (Per Instance)
| Component | Spec |
|-----------|------|
| CPU | 2 vCPU |
| RAM | 4 GB |
| Disk | 20 GB SSD |
| Network | 1 Gbps |

### Production Cluster (Recommended)
| Component | Spec |
|-----------|------|
| API Instances | 3+ (behind load balancer) |
| PostgreSQL | Managed (AWS RDS / Azure / GCP Cloud SQL) |
| Redis | Managed (ElastiCache / Azure Cache / Memorystore) |
| Load Balancer | Application LB (ALB/NGINX) |
| CDN | For static assets |

---

## Environment Variables

### Required
```
# Database
DATABASE_URL=postgresql://user:pass@host:5432/justice_ai

# Security
SECRET_KEY=your-256-bit-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
MODEL_PROVIDER=openai  # or anthropic, mock
MODEL_NAME=gpt-4o-mini
MODEL_API_KEY=sk-...

# Embeddings
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# RAG
RAG_TOP_K=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Upload
MAX_UPLOAD_SIZE=10485760

# Tenant
DEFAULT_TENANT_ID=default
```

### Optional
```
# Redis (if separate)
REDIS_URL=redis://localhost:6379/0

# Monitoring
SENTRY_DSN=https://...
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=https://app.justice-ai.com,https://staging.justice-ai.com
```

---

## Docker Deployment

### Build
```
docker build -t justice-ai:latest .
docker build -t justice-ai:v1.0.0 .
```

### Run (Single Container)
```
docker run -d   --name justice-ai   --restart unless-stopped   -p 8000:8000   -e DATABASE_URL=postgresql://user:pass@host:5432/justice_ai   -e SECRET_KEY=your-secret   -e MODEL_PROVIDER=openai   -e MODEL_API_KEY=sk-...   -v justice-ai-uploads:/app/uploads   justice-ai:latest
```

### Docker Compose (Local Stack)
```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/justice_ai
      - SECRET_KEY=dev-secret-change-in-prod
      - MODEL_PROVIDER=mock
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/app/uploads

  db:
    image: pgvector/pgvector:pg18
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=justice_ai
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

### Run Compose
```
docker-compose up -d
docker-compose logs -f api
docker-compose down -v  # cleanup
```

---

## Kubernetes Deployment

### Namespace
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: justice-ai
```

### ConfigMap
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: justice-ai-config
  namespace: justice-ai
data:
  MODEL_PROVIDER: "openai"
  EMBEDDING_PROVIDER: "sentence-transformers"
  RAG_TOP_K: "5"
  CHUNK_SIZE: "1000"
  CHUNK_OVERLAP: "200"
```

### Secret
```yaml
# k8s/secret.yaml (apply with kubectl apply -f)
apiVersion: v1
kind: Secret
metadata:
  name: justice-ai-secrets
  namespace: justice-ai
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:pass@postgres:5432/justice_ai"
  SECRET_KEY: "your-256-bit-secret"
  MODEL_API_KEY: "sk-..."
```

### Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: justice-ai
  namespace: justice-ai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: justice-ai
  template:
    metadata:
      labels:
        app: justice-ai
    spec:
      containers:
      - name: api
        image: justice-ai:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: justice-ai-config
        - secretRef:
            name: justice-ai-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

### Service
```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: justice-ai
  namespace: justice-ai
spec:
  selector:
    app: justice-ai
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

### Ingress
```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: justice-ai
  namespace: justice-ai
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.justice-ai.com
    secretName: justice-ai-tls
  rules:
  - host: api.justice-ai.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: justice-ai
            port:
              number: 80
```

### Apply
```
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl get pods -n justice-ai
kubectl logs -n justice-ai -l app=justice-ai
```

---

## Database Migration (Production)

### Pre-deployment
```
# 1. Backup
pg_dump -h $DB_HOST -U $DB_USER -d justice_ai > backup_$(date +%Y%m%d_%H%M).sql

# 2. Run migrations (in CI/CD or manually)
alembic upgrade head

# 3. Verify
alembic current
psql -h $DB_HOST -U $DB_USER -d justice_ai -c "\dt"
```

### Rollback
```
# If migration breaks
alembic downgrade -1

# Or restore backup
psql -h $DB_HOST -U $DB_USER -d justice_ai < backup_20261020_1400.sql
```

---

## Health Checks & Monitoring

### Endpoints
| Endpoint | Purpose | Expected |
|----------|---------|----------|
| GET /health/live | Liveness (k8s) | {"status":"alive"} |
| GET /health/ready | Readiness (k8s) | {"status":"ready"} |

### Prometheus Metrics (Planned)
```yaml
# Add to deployment
- name: PROMETHEUS_MULTIPROC_DIR
  value: /tmp/prometheus
```

### Log Aggregation
- Format: JSON structured logs
- Fields: timestamp, level, service, trace_id, tenant_id, message
- Destination: Loki / Elasticsearch / CloudWatch

---

## SSL/TLS

### Let's Encrypt (via cert-manager)
```yaml
# In Ingress
annotations:
  cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.justice-ai.com
    secretName: justice-ai-tls
```

### Custom Certificate
```
# Create secret manually
kubectl create secret tls justice-ai-tls   --cert=path/to/cert.pem   --key=path/to/key.pem   -n justice-ai
```

---

## Scaling

### Horizontal Pod Autoscaler
```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: justice-ai
  namespace: justice-ai
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: justice-ai
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Database Scaling
- Read replicas: For RAG query distribution
- Connection pooling: PgBouncer (recommended)
- Partitioning: By tenant_id (future)

---

## Disaster Recovery

### RTO/RPO Targets
| Metric | Target |
|--------|--------|
| RTO (Recovery Time Objective) | < 1 hour |
| RPO (Recovery Point Objective) | < 15 minutes |

### Backup Schedule
| Type | Frequency | Retention |
|------|-----------|-----------|
| Full DB | Daily | 30 days |
| Incremental | Hourly | 7 days |
| Config/Secrets | On change | 90 days |

### Runbook
1. Detect: Alert from monitoring (DB down, API 5xx > 5%)
2. Assess: Check logs, DB connectivity, pod status
3. Mitigate: Failover to standby, scale pods, restart
4. Recover: Restore from backup if data loss
5. Postmortem: Document root cause, action items

---

## Rollback Procedure

### Application
```
# Kubernetes
kubectl rollout undo deployment/justice-ai -n justice-ai

# Docker Compose
docker-compose down
docker tag justice-ai:previous justice-ai:latest
docker-compose up -d
```

### Database
```
# Alembic
alembic downgrade -1

# Or restore
psql -h $DB_HOST -U $DB_USER -d justice_ai < backup_latest.sql
```

---

## Security Checklist (Pre-Deploy)

- [ ] SECRET_KEY rotated, 256-bit, in secrets manager
- [ ] MODEL_API_KEY in secrets, not ConfigMap
- [ ] Database TLS enabled (sslmode=require)
- [ ] Redis TLS enabled
- [ ] Ingress TLS terminated (cert-manager)
- [ ] CORS origins restricted to known domains
- [ ] Rate limiting configured
- [ ] Security headers (CSP, HSTS, X-Frame-Options)
- [ ] Dependency scan passed (pip-audit, trivy)
- [ ] Container runs as non-root user
- [ ] Read-only root filesystem (where possible)

---

*Deployment guide verified for Docker, Docker Compose, and Kubernetes*