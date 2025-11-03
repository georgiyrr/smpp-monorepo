# 🚀 SMPP Server Monorepo

Complete SMPP HLR Gateway system with shared infrastructure and two gateway variants.

## 📦 Structure

```
smpp-monorepo/
├── infrastructure/              # Shared services (Git submodule)
│   ├── PostgreSQL 16
│   ├── Redis 7
│   ├── Prometheus
│   └── Grafana
├── smpp-hlr-gateway/           # Original Gateway (Git submodule)
│   ├── Async SMPP Server
│   ├── HLR Lookup Client
│   ├── DLR Logging (UNDELIV)
│   └── Port: 2775, Metrics: 9090
└── smpp-hlr-gateway-dlv/       # Enhanced Gateway (Git submodule) 🆕
    ├── Async SMPP Server
    ├── HLR Lookup Client
    ├── Full DLR via SMPP (DELIVRD/UNDELIV)
    └── Port: 2776, Metrics: 9091
```

## 🎯 Gateway Variants

### Original Gateway (`smpp-hlr-gateway`)
- **Port:** 2775
- **Metrics:** 9090
- **Behavior:**
  - ✅ Valid numbers → Rejected with `ESME_RINVDSTADR`
  - ✅ Invalid numbers → Accepted + UNDELIV logged
- **Use case:** Simple validation and filtering

### Enhanced Gateway DLV (`smpp-hlr-gateway-dlv`) 🆕
- **Port:** 2776
- **Metrics:** 9091
- **Behavior:**
  - ✅ Valid numbers → Accepted + **DELIVRD sent via SMPP**
  - ✅ Invalid numbers → Accepted + **UNDELIV sent via SMPP**
- **Use case:** Full SMPP compliance with DLR delivery

## 🏃 Quick Start

### 1. Clone with submodules

```bash
git clone --recursive https://github.com/georgiyrr/smpp-monorepo.git
cd smpp-monorepo
```

Or if already cloned:

```bash
git submodule update --init --recursive
```

### 2. Start infrastructure

```bash
cd infrastructure
cp .env.example .env
nano .env  # Set passwords
docker-compose up -d
cd ..
```

### 3. Start SMPP Gateway (choose one or both)

#### Option A: Original Gateway

```bash
cd smpp-hlr-gateway
cp .env.example .env
nano .env  # Set HLR credentials
docker-compose up -d
cd ..
```

#### Option B: Enhanced Gateway DLV 🆕

```bash
cd smpp-hlr-gateway-dlv
cp .env.example .env
nano .env  # Set HLR credentials
docker-compose up -d
cd ..
```

#### Option C: Both Gateways

```bash
# Start original gateway
cd smpp-hlr-gateway
docker-compose up -d
cd ..

# Start enhanced gateway DLV
cd smpp-hlr-gateway-dlv
docker-compose up -d
cd ..
```

### 4. Verify

```bash
# Check all services
docker ps

# Infrastructure
curl http://localhost:9091/metrics    # Prometheus
open http://localhost:3001            # Grafana (admin/password)

# Original Gateway
curl http://localhost:9090/metrics
docker logs smpp-gateway -f

# Enhanced Gateway DLV
curl http://localhost:9091/metrics
docker logs smpp-gateway-dlv -f
```

## 🔄 Working with Submodules

### Update all submodules to latest

```bash
git submodule update --remote --merge
```

### Make changes in a submodule

```bash
# Navigate to submodule
cd infrastructure  # or smpp-hlr-gateway or smpp-hlr-gateway-dlv

# Work on the submodule
git checkout main
git pull origin main
# ... make your changes ...
git add .
git commit -m "Update: your changes"
git push origin main

# Return to parent and update reference
cd ..
git add infrastructure  # or smpp-hlr-gateway or smpp-hlr-gateway-dlv
git commit -m "Update submodule to latest"
git push origin main
```

### Clone individual repositories

Each submodule is an independent repository:

```bash
# Clone just infrastructure
git clone https://github.com/georgiyrr/shared-infrastructure.git

# Clone just original gateway
git clone https://github.com/georgiyrr/smpp-hlr-gateway.git

# Clone just enhanced gateway DLV
git clone https://github.com/georgiyrr/smpp-hlr-gateway-dlv.git

# Use infrastructure for other projects
cd my-other-project
docker-compose -f ../shared-infrastructure/docker-compose.yml up -d
```

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│   SMPP HLR Gateway (Original)       │
│  (smpp-hlr-gateway submodule)       │
│                                     │
│  • SMPP Server          :2775       │
│  • TMT Velocity HLR API             │
│  • UNDELIV Logging                  │
│  • Prometheus Metrics   :9090       │
└──────────────┬──────────────────────┘
               │
               │ uses
               ▼
┌─────────────────────────────────────┐
│    Shared Infrastructure            │
│   (infrastructure submodule)        │
│                                     │
│  • PostgreSQL 16        :5432       │
│  • Redis 7              :6379       │
│  • Prometheus           :9091       │
│  • Grafana              :3001       │
└──────────────┬──────────────────────┘
               ▲
               │ uses
               │
┌──────────────┴──────────────────────┐
│   SMPP HLR Gateway DLV 🆕           │
│  (smpp-hlr-gateway-dlv submodule)   │
│                                     │
│  • SMPP Server          :2776       │
│  • TMT Velocity HLR API             │
│  • Full DLR via SMPP                │
│  • DELIVRD + UNDELIV                │
│  • Prometheus Metrics   :9091       │
└─────────────────────────────────────┘
```

## 📊 Port Allocation

| Service | Port | Purpose |
|---------|------|---------|
| **Infrastructure** | | |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Prometheus | 9091 | Metrics Collection |
| Grafana | 3001 | Dashboards |
| **Original Gateway** | | |
| SMPP | 2775 | SMPP Protocol |
| Metrics | 9090 | Prometheus Metrics |
| **Enhanced Gateway DLV** | | |
| SMPP | 2776 | SMPP Protocol |
| Metrics | 9091 | Prometheus Metrics |

## 🧪 Testing

### Test Original Gateway

```bash
cd smpp-hlr-gateway

# Test valid number (should be rejected)
python examples/test_client.py --port 2775 --msisdn 380661019528
# Expected: ESME_RINVDSTADR

# Test invalid number (should be accepted + UNDELIV logged)
python examples/test_client.py --port 2775 --msisdn 40722570240999
# Expected: ESME_ROK + DLR in logs
```

### Test Enhanced Gateway DLV

```bash
cd smpp-hlr-gateway-dlv

# Test valid number (should be accepted + DELIVRD sent)
python examples/test_client.py --port 2776 --msisdn 380661019528
# Expected: ESME_ROK + DELIVRD DLR via SMPP

# Test invalid number (should be accepted + UNDELIV sent)
python examples/test_client.py --port 2776 --msisdn 40722570240999
# Expected: ESME_ROK + UNDELIV DLR via SMPP
```

### Test Infrastructure

```bash
cd infrastructure
make healthcheck
```

## 📈 Monitoring

### Access Points

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Grafana | http://localhost:3001 | admin / (from .env) |
| Prometheus | http://localhost:9091 | - |
| Original Gateway Metrics | http://localhost:9090/metrics | - |
| Enhanced Gateway DLV Metrics | http://localhost:9091/metrics | - |

### Grafana Setup

1. Open http://localhost:3001
2. Login with credentials from infrastructure/.env
3. Add Prometheus data source: `http://prometheus:9090`
4. Create dashboards for both gateways

### Prometheus Queries

```promql
# Original Gateway
rate(submit_total{gateway="original"}[5m])

# Enhanced Gateway DLV
rate(submit_total{gateway="dlv"}[5m])
rate(delivrd_total[5m])

# Combined HLR requests
sum(rate(hlr_requests_total[5m]))

# Cache hit rate
rate(hlr_cache_hits_total[5m]) / (rate(hlr_cache_hits_total[5m]) + rate(hlr_cache_misses_total[5m]))
```

## 🛠️ Development

### With PyCharm

PyCharm automatically detects multiple Git roots:

- `smpp-monorepo/` (monorepo root)
- `infrastructure/` (submodule)
- `smpp-hlr-gateway/` (submodule)
- `smpp-hlr-gateway-dlv/` (submodule) 🆕

You can:
- Commit to each repository independently
- See all repos in VCS → Git → Remotes
- Use VCS → Update Project to pull all repos

### Environment Setup

```bash
# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies for development
cd smpp-hlr-gateway && pip install -r requirements.txt && cd ..
cd smpp-hlr-gateway-dlv && pip install -r requirements.txt && cd ..
```

## 🔧 Configuration

### Infrastructure (.env)

```bash
POSTGRES_PASSWORD=your_secure_password
GRAFANA_PASSWORD=your_grafana_password
```

### Original Gateway (.env)

```bash
SMPP_SYSTEM_ID=testuser
SMPP_PASSWORD=testpass
HLR_API_KEY=your_tmt_api_key
HLR_API_SECRET=your_tmt_api_secret
DB_PASSWORD=smpp_password  # Must match infrastructure
```

### Enhanced Gateway DLV (.env)

```bash
SMPP_SYSTEM_ID=testuser
SMPP_PASSWORD=testpass
HLR_API_KEY=your_tmt_api_key
HLR_API_SECRET=your_tmt_api_secret
DB_PASSWORD=smpp_password  # Must match infrastructure
```

## 🆚 Gateway Comparison

| Feature | Original Gateway | Enhanced Gateway DLV |
|---------|------------------|----------------------|
| **SMPP Port** | 2775 | 2776 |
| **Metrics Port** | 9090 | 9091 |
| **Valid Numbers** | Rejected | Accepted + DELIVRD |
| **Invalid Numbers** | Accepted + Logged | Accepted + UNDELIV |
| **DLR Delivery** | Logged only | Sent via SMPP |
| **Use Case** | Simple filtering | Full SMPP compliance |
| **Production** | ✅ | ✅ |

## 📚 Documentation

- [Infrastructure Documentation](infrastructure/README.md)
- [Original Gateway Documentation](smpp-hlr-gateway/README.md)
- [Enhanced Gateway DLV Documentation](smpp-hlr-gateway-dlv/README.md) 🆕
- [Gateway Quick Start](smpp-hlr-gateway/QUICK_START.md)
- [Deployment Guide](DEPLOYMENT.md)

## 🚀 Deployment

### Production Checklist

- [ ] Change all default passwords
- [ ] Set real TMT API credentials
- [ ] Configure firewalls (only internal network access)
- [ ] Set up automated backups
- [ ] Configure monitoring alerts
- [ ] Enable log rotation
- [ ] Review resource limits
- [ ] Test failover scenarios

### Scaling

```bash
# Scale infrastructure
cd infrastructure
docker-compose up -d --scale redis=3

# Run multiple gateway instances
cd smpp-hlr-gateway
docker-compose up -d --scale smpp-gateway=3
```

## 🔄 Maintenance

### Daily

```bash
# Check health
docker ps
cd infrastructure && make healthcheck

# View logs
docker-compose logs -f
```

### Weekly

```bash
# Backup database
cd infrastructure && make backup

# Update submodules
git submodule update --remote --merge
```

### Monthly

```bash
# Clean old backups
cd infrastructure && find backups/ -mtime +30 -delete

# Review metrics and optimize
open http://localhost:3001
```

## 🚨 Troubleshooting

### Submodule not cloned

```bash
git submodule update --init --recursive
```

### Can't connect to infrastructure

```bash
# Check infrastructure is running
cd infrastructure
docker-compose ps

# Check network
docker network inspect shared-network

# Restart infrastructure
docker-compose restart
```

### Port conflicts

```bash
# Check what's using ports
sudo lsof -i :2775
sudo lsof -i :2776
sudo lsof -i :9090
sudo lsof -i :9091

# Stop conflicting services or change ports in .env
```

## 📝 License

MIT License

## 👥 Repositories

- **Main Monorepo:** https://github.com/georgiyrr/smpp-monorepo
- **Shared Infrastructure:** https://github.com/georgiyrr/shared-infrastructure
- **Original Gateway:** https://github.com/georgiyrr/smpp-hlr-gateway
- **Enhanced Gateway DLV:** https://github.com/georgiyrr/smpp-hlr-gateway-dlv 🆕

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the relevant repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 💬 Support

For issues and questions:
- GitHub Issues: Create an issue in the relevant repository
- Documentation: Check README files in each component

---

**Built with ❤️ using Python 3.11+, asyncio, Docker, and modern async libraries**