# 🚀 SMPP Server Monorepo

Complete SMPP HLR Gateway system with shared infrastructure.

## 📦 Structure
smpp_server/
├── infrastructure/          # Shared services (Git submodule)
│   ├── PostgreSQL 16
│   ├── Redis 7
│   ├── Prometheus
│   └── Grafana
└── smpp-hlr-gateway/       # SMPP Gateway (Git submodule)
├── Async SMPP Server
├── HLR Lookup Client
└── Metrics

## 🏃 Quick Start

### 1. Clone with submodules
```bash
git clone --recursive https://github.com/georgiyrr/smpp-monorepo.git
cd smpp_server
Or if already cloned:
bashgit submodule update --init --recursive
2. Start infrastructure
bashcd infrastructure
cp .env.example .env
docker-compose up -d
cd ..
3. Start SMPP Gateway
bashcd smpp-hlr-gateway  
cp .env.example .env
docker-compose up -d
cd ..
4. Verify
bash# Check all services
docker ps

# Infrastructure metrics
curl http://localhost:9091/metrics    # Prometheus
open http://localhost:3001            # Grafana (admin/admin)

# Gateway metrics
curl http://localhost:9090/metrics

# Gateway logs
docker logs smpp-gateway -f
🔄 Working with Submodules
Update all submodules to latest
bashgit submodule update --remote --merge
Make changes in a submodule
bash# Navigate to submodule
cd infrastructure  # or smpp-hlr-gateway

# Work on the submodule
git checkout main
git pull origin main
# ... make your changes ...
git add .
git commit -m "Update: your changes"
git push origin main

# Return to parent and update reference
cd ..
git add infrastructure  # or smpp-hlr-gateway
git commit -m "Update infrastructure to latest"
git push origin main
Clone individual repositories
Each submodule is an independent repository:
bash# Clone just infrastructure
git clone https://github.com/georgiyrr/shared-infrastructure.git

# Clone just gateway
git clone https://github.com/georgiyrr/smpp-hlr-gateway.git

# Use infrastructure for other projects
cd my-other-project
docker-compose -f ../shared-infrastructure/docker-compose.yml up -d
🏗️ Architecture
┌─────────────────────────────────────┐
│      SMPP HLR Gateway               │
│   (smpp-hlr-gateway submodule)      │
│                                     │
│  • SMPP Server          :2775       │
│  • TMT Velocity HLR API             │
│  • Redis Cache                      │
│  • PostgreSQL Storage               │
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
└─────────────────────────────────────┘
📚 Documentation

Infrastructure Documentation
Gateway Documentation
Gateway Quick Start
Deployment Guide

🛠️ Development with PyCharm
PyCharm automatically detects multiple Git roots:

smpp_server/ (monorepo root)
infrastructure/ (submodule)
smpp-hlr-gateway/ (submodule)

You can:

Commit to each repository independently
See all repos in VCS → Git → Remotes
Use VCS → Update Project to pull all repos

🧪 Testing
bash# Test infrastructure
cd infrastructure
make healthcheck

# Test gateway
cd smpp-hlr-gateway
python examples/test_client.py --msisdn 380501234567
📊 Monitoring

Grafana: http://localhost:3001 (admin/admin)
Prometheus: http://localhost:9091
Gateway Metrics: http://localhost:9090/metrics

📝 License
MIT
👥 Repositories

Main Monorepo
Shared Infrastructure
SMPP HLR Gateway
