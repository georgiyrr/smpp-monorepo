# ⚡ Quick Start Guide

Get SMPP HLR Gateway running in 5 minutes!

## 📋 Prerequisites

- Docker & Docker Compose installed
- TMT Velocity API credentials

## 🚀 Installation

### Step 1: Setup Infrastructure (2 min)

```bash
# Create and enter infrastructure directory
mkdir -p ~/projects/infrastructure
cd ~/projects/infrastructure

# Create necessary files and directories
mkdir -p volumes/{postgres,redis,prometheus,grafana} init-scripts backups

# Download infrastructure files (copy from artifacts)
# Or use git if in repository
```

**Create `infrastructure/.env`:**
```bash
cat > .env << 'EOF'
POSTGRES_PASSWORD=MySecurePassword123!
GRAFANA_PASSWORD=MyGrafanaPass123!
EOF
```

**Start infrastructure:**
```bash
docker-compose up -d

# Wait 10 seconds for initialization
sleep 10

# Verify
docker-compose ps
# All services should show "Up (healthy)"
```

### Step 2: Setup SMPP Gateway (3 min)

```bash
cd ~/projects/smpp_hlr_gateway

# Configure
cat > .env << 'EOF'
SMPP_SYSTEM_ID=testuser
SMPP_PASSWORD=testpass
HLR_API_KEY=your_tmt_api_key
HLR_API_SECRET=your_tmt_api_secret
DB_PASSWORD=smpp_password_change_me
LOG_LEVEL=INFO
EOF

# Build and start
docker-compose build
docker-compose up -d

# Watch startup
docker-compose logs -f
```

**Expected logs:**
```json
{"event": "redis_connected"}
{"event": "db_connected"}
{"event": "cache_warmup_complete", "records_loaded": 0}
{"event": "smpp_server_started", "port": 2776}
```

Press `Ctrl+C` when you see "smpp_server_started"

## ✅ Verify Installation

```bash
# 1. Check all containers
docker ps

# Should see:
# - smpp-gateway
# - shared-postgres
# - shared-redis
# - shared-prometheus
# - shared-grafana

# 2. Test SMPP
cd ~/projects/smpp_hlr_gateway
python examples/test_client.py --msisdn 380661019528

# 3. Check database
cd ~/projects/infrastructure
docker exec -it shared-postgres psql -U admin -d smpp_hlr -c "SELECT count(*) FROM hlr_lookups;"

# 4. Check metrics
curl http://localhost:9091/metrics | head -20
```

## 🎯 Quick Commands

```bash
# Infrastructure
cd ~/projects/infrastructure
make up      # Start all
make down    # Stop all
make logs    # View logs
make stats   # Show usage
make backup  # Backup DB

# SMPP Gateway
cd ~/projects/smpp_hlr_gateway
docker-compose logs -f      # View logs
docker-compose restart      # Restart
make healthcheck            # Check health
make metrics                # View metrics
```

## 🌐 Access Points

| Service | URL                           | Credentials |
|---------|-------------------------------|-------------|
| SMPP Gateway | `localhost:2776`              | testuser / testpass |
| Metrics | http://localhost:9091/metrics | - |
| Prometheus | http://localhost:9091         | - |
| Grafana | http://localhost:3001         | admin / (from .env) |
| PostgreSQL | `localhost:5432`              | admin / (from .env) |
| Redis | `localhost:6379`              | - |

## 📊 Test Scenarios

### Scenario 1: Valid Number (Rejected)
```bash
python examples/test_client.py --msisdn 380661019528
# Expected: ESME_RINVDSTADR (rejected)
```

### Scenario 2: Invalid Number (Accepted + DELIVRD)
```bash
python examples/test_client.py --msisdn 40722570240999
# Expected: ESME_ROK + DELIVRD DLR in logs
```

### Scenario 3: Check Database
```bash
cd ~/projects/infrastructure
docker exec shared-postgres psql -U admin -d smpp_hlr -c \
  "SELECT msisdn, classification, created_at FROM hlr_lookups ORDER BY created_at DESC LIMIT 5;"
```

## 🛑 Stop Everything

```bash
# Stop gateway
cd ~/projects/smpp_hlr_gateway
docker-compose down

# Stop infrastructure
cd ~/projects/infrastructure
docker-compose down

# Or stop both
docker stop smpp-gateway shared-postgres shared-redis shared-prometheus shared-grafana
```

## 🆘 Common Issues

### "Can't connect to shared-postgres"
```bash
# Check if infrastructure is running
cd ~/projects/infrastructure
docker-compose ps

# If not, start it first
docker-compose up -d
sleep 10
```

### "Network shared-network not found"
```bash
# Create network manually
docker network create shared-network

# Or start infrastructure first
cd ~/projects/infrastructure
docker-compose up -d
```

### "Permission denied" errors
```bash
# Fix volumes permissions
sudo chown -R $(whoami):$(whoami) volumes/
```

## 📚 Next Steps

1. **Read full documentation:**
   - `infrastructure/README.md`
   - `smpp_hlr_gateway/README.md`
   - `DEPLOYMENT.md`

2. **Configure production settings:**
   - Change all passwords
   - Set real TMT API credentials
   - Configure monitoring alerts

3. **Enable backups:**
   ```bash
   cd ~/projects/infrastructure
   # Add to crontab
   crontab -e
   # Add: 0 2 * * * cd /path/to/infrastructure && make backup
   ```

4. **Monitor:**
   - Open Grafana: http://localhost:3001
   - Add Prometheus data source
   - Import dashboards

---

**🎉 You're all set! Gateway is ready for 1M lookups/day!**

Need help? Check `DEPLOYMENT.md` for detailed instructions.