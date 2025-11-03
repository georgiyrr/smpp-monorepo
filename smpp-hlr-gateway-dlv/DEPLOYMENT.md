# 🚀 Deployment Guide

Complete guide for deploying SMPP HLR Gateway with shared infrastructure.

## 📁 Project Structure

```
~/projects/
├── infrastructure/               # Shared services
│   ├── docker-compose.yml
│   ├── .env
│   ├── init-scripts/
│   │   ├── 01-init-databases.sh
│   │   └── 02-create-smpp-tables.sql
│   ├── prometheus.yml
│   ├── Makefile
│   └── volumes/                  # Data storage
│       ├── postgres/
│       ├── redis/
│       ├── prometheus/
│       └── grafana/
│
└── smpp-hlr-gateway/            # SMPP Gateway service
    ├── docker-compose.yml
    ├── .env
    ├── Dockerfile
    ├── main.py
    ├── src/
    └── ...
```

## 🎯 Step-by-Step Deployment

### Step 1: Setup Infrastructure

```bash
# Create infrastructure directory
mkdir -p ~/projects/infrastructure
cd ~/projects/infrastructure

# Create directory structure
mkdir -p volumes/{postgres,redis,prometheus,grafana}
mkdir -p init-scripts backups

# Copy all infrastructure files from artifacts:
# - docker-compose.yml
# - .env.example
# - init-scripts/01-init-databases.sh
# - init-scripts/02-create-smpp-tables.sql
# - prometheus.yml
# - Makefile

# Make init script executable
chmod +x init-scripts/01-init-databases.sh

# Configure environment
cp .env.example .env
nano .env  # Edit passwords!
```

**Important: Change default passwords in `.env`:**
```bash
POSTGRES_PASSWORD=your_super_secure_password_here
GRAFANA_PASSWORD=your_grafana_password_here
```

### Step 2: Start Infrastructure

```bash
cd ~/projects/infrastructure

# Start all infrastructure services
make up

# Or manually:
docker-compose up -d

# Verify all services are healthy
make ps

# Expected output:
# shared-postgres   Up (healthy)
# shared-redis      Up (healthy)
# shared-prometheus Up
# shared-grafana    Up
```

### Step 3: Verify Infrastructure

```bash
# Check PostgreSQL
make psql
# Should connect successfully
\l  # List databases
\q  # Quit

# Check Redis
make redis-cli
PING  # Should return PONG
exit

# Check Prometheus
curl http://localhost:9091/api/v1/targets

# Check Grafana
open http://localhost:3000
# Login: admin / (your password from .env)
```

### Step 4: Setup SMPP Gateway

```bash
cd ~/projects/smpp-hlr-gateway

# Update docker-compose.yml
# Replace the old docker-compose.yml with the new one from artifacts
# Key changes:
# - Removed redis service (using shared-redis)
# - Added external network: shared-network
# - Added DB_* environment variables

# Update .env
cp .env.example .env
nano .env

# Important: DB_PASSWORD must match the password from infrastructure init script
DB_PASSWORD=smpp_password_change_me  # Change this!
```

### Step 5: Start SMPP Gateway

```bash
cd ~/projects/smpp-hlr-gateway

# Build and start
docker-compose build
docker-compose up -d

# Watch logs
docker-compose logs -f smpp-gateway

# Expected logs:
# ✓ redis_connected
# ✓ db_connected
# ✓ cache_warmup_complete (if enabled)
# ✓ hlr_client_initialized
# ✓ smpp_server_started
```

### Step 6: Verify Integration

```bash
# Check network connectivity
docker network inspect shared-network

# Should see:
# - shared-postgres
# - shared-redis
# - smpp-gateway

# Test database connection
docker exec smpp-gateway python -c "
import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect(
        host='shared-postgres',
        port=5432,
        database='smpp_hlr',
        user='smpp_user',
        password='smpp_password_change_me'
    )
    print('✓ Database connected')
    await conn.close()

asyncio.run(test())
"

# Test Redis connection
docker exec smpp-gateway python -c "
import redis
r = redis.Redis(host='shared-redis', port=6379, db=0)
print('PING:', r.ping())
"
```

## 🧪 Testing

### Test 1: SMPP Connection

```bash
cd ~/projects/smpp-hlr-gateway

# Test with valid number (should be rejected)
python examples/test_client.py --msisdn 380661019528

# Test with invalid number (should be accepted + DELIVRD)
python examples/test_client.py --msisdn 40722570240999
```

### Test 2: Database Recording

```bash
# Check if lookups are saved to database
cd ~/projects/infrastructure
make psql-smpp

# In PostgreSQL:
SELECT count(*) FROM hlr_lookups;
SELECT * FROM hlr_lookups ORDER BY created_at DESC LIMIT 5;
\q
```

### Test 3: Cache Warmup

```bash
# Restart gateway to test warmup
cd ~/projects/smpp-hlr-gateway
docker-compose restart

# Check logs for warmup
docker-compose logs smpp-gateway | grep warmup

# Should see:
# cache_warmup_started
# cache_warmup_complete records_loaded=X
```

## 📊 Monitoring

### Prometheus Metrics

```bash
# SMPP Gateway metrics
curl http://localhost:9091/metrics | grep hlr_

# Infrastructure metrics
curl http://localhost:9091/api/v1/query?query=up
```

### Grafana Dashboards

1. Open http://localhost:3001
2. Add Prometheus data source:
   - URL: `http://prometheus:9091`
3. Create dashboard with queries:
   ```promql
   submit_total
   hlr_requests_total
   rate(hlr_latency_seconds_sum[5m])
   ```

### Database Monitoring

```bash
cd ~/projects/infrastructure

# Show statistics
make stats

# Monitor connections
make monitor

# Check table sizes
make psql-smpp
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## 🔄 Maintenance

### Daily Tasks

```bash
# Check service health
cd ~/projects/infrastructure
make check-health

# Check disk usage
make stats
```

### Weekly Tasks

```bash
# Backup databases
cd ~/projects/infrastructure
make backup

# Refresh materialized view
make refresh-mv

# Vacuum database
make vacuum
```

### Monthly Tasks

```bash
# Archive old backups
cd ~/projects/infrastructure
find backups/ -name "*.sql.gz" -mtime +30 -delete

# Review metrics in Grafana
open http://localhost:3001

# Check for updates
docker-compose pull
```

## 🚨 Troubleshooting

### Gateway can't connect to PostgreSQL

```bash
# Check if infrastructure is running
cd ~/projects/infrastructure
docker-compose ps

# Check network
docker network inspect shared-network

# Test connection from gateway container
docker exec smpp-gateway ping shared-postgres

# Check PostgreSQL logs
make logs-pg
```

### Gateway can't connect to Redis

```bash
# Check Redis
cd ~/projects/infrastructure
make redis-cli
PING

# Check from gateway
docker exec smpp-gateway redis-cli -h shared-redis ping
```

### Database is full

```bash
cd ~/projects/infrastructure

# Check sizes
make stats

# Clean old data
make psql-smpp
DELETE FROM hlr_lookups WHERE created_at < NOW() - INTERVAL '30 days';
VACUUM ANALYZE hlr_lookups;
\q

# Or use automated cleanup (add to crontab)
echo "0 3 * * 0 docker exec shared-postgres psql -U admin -d smpp_hlr -c \"DELETE FROM hlr_lookups WHERE created_at < NOW() - INTERVAL '90 days'; VACUUM ANALYZE hlr_lookups;\"" | crontab -
```

## 🔐 Security Checklist

- [ ] Changed all default passwords in both `.env` files
- [ ] PostgreSQL password in infrastructure/.env
- [ ] DB_PASSWORD in smpp-hlr-gateway/.env matches init script
- [ ] SMPP_PASSWORD changed from default
- [ ] HLR_API_KEY and HLR_API_SECRET set to real values
- [ ] Grafana admin password changed
- [ ] Ports 5432 and 6379 not exposed to internet (only internal)
- [ ] Regular backups scheduled
- [ ] Monitoring and alerts configured

## 📦 Adding More Services

To add another service that uses shared infrastructure:

```yaml
# your-service/docker-compose.yml
services:
  your-service:
    build: ..
    environment:
      DB_HOST: shared-postgres
      DB_PORT: 5432
      DB_NAME: your_database  # Created in init script
      REDIS_URL: redis://shared-redis:6379/3  # Use different DB number
    networks:
      - shared-network

networks:
  shared-network:
    external: true
```

## 🎓 Next Steps

1. **Set up automated backups** - See infrastructure/Makefile
2. **Configure Grafana dashboards** - Import PostgreSQL and Redis dashboards
3. **Set up alerting** - Configure Prometheus Alertmanager
4. **Add SSL/TLS** - For production deployment
5. **Scale** - Add read replicas for PostgreSQL if needed

---

**Need help?** Check the README files:
- `infrastructure/README.md`
- `smpp-hlr-gateway/README.md`