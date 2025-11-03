# SMPP HLR Gateway

Asynchronous SMPP gateway with HLR lookup integration for number validation and filtering.

## 🎯 Overview

This gateway performs real-time HLR (Home Location Register) lookups via TMT Velocity API for every incoming SubmitSM request. Based on the HLR result, it implements a **reverse filtering logic**:

- **Valid numbers** (error=0, status=0, present=yes) → **Rejected immediately** with `ESME_RINVDSTADR`
- **Invalid numbers** (any error or status!=0) → **Accepted** with SubmitSmResp OK, then **DELIVRD DLR** sent later

This is useful for scenarios where you want to filter out valid numbers and only process invalid/unreachable ones.

## 🏗️ Architecture

```
┌─────────────┐     SubmitSM      ┌──────────────┐
│ SMPP Client │ ───────────────►  │ SMPP Gateway │
└─────────────┘                   │   (Python)   │
                                  └───────┬──────┘
                                          │
                    ┌─────────────────────┼─────────────────┐
                    │                     │                 │
                    ▼                     ▼                 ▼
              ┌─────────┐           ┌─────────┐      ┌─────────┐
              │  Redis  │           │   TMT   │      │ Metrics │
              │  Cache  │           │ Velocity│      │  :9091  │
              └─────────┘           │ HLR API │      └─────────┘
                                    └─────────┘
```

## 📋 Features

- ✅ Async SMPP server (non-blocking)
- ✅ HLR lookup with TMT Velocity API integration
- ✅ Redis caching (configurable TTL)
- ✅ Prometheus metrics
- ✅ Structured logging (JSON/console)
- ✅ Docker containerization
- ✅ Health checks
- ✅ Graceful shutdown
- ✅ Comprehensive tests

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- TMT Velocity API credentials

### 1. Clone and Configure

```bash
# Copy environment template
cp .env.example .env

# Edit with your TMT credentials
nano .env
```

Required environment variables:
```bash
HLR_API_KEY=your_tmt_api_key
HLR_API_SECRET=your_tmt_api_secret
SMPP_SYSTEM_ID=testuser
SMPP_PASSWORD=testpass
```

### 2. Start Services

```bash
docker-compose up -d
```

### 3. Verify Health

```bash
# Check container health
docker-compose ps

# View logs
docker-compose logs -f smpp-gateway

# Check metrics
curl http://localhost:9091/metrics
```

## 📡 Testing

### Send Test SMPP Message

Using `smpplib` Python client:

```python
import smpplib.client

client = smpplib.client.Client('localhost', 2776)

# Bind
client.connect()
client.bind_transmitter(system_id='testuser', password='testpass')

# Test with VALID number (will be REJECTED)
pdu = client.send_message(
    source_addr='1234',
    destination_addr='13476841841',  # Valid US number
    short_message=b'Test message'
)
# Expected: Command status = ESME_RINVDSTADR (0x0000000B)

# Test with INVALID number (will be ACCEPTED + DELIVRD later)
pdu = client.send_message(
    source_addr='1234',
    destination_addr='40722570240999',  # Invalid number
    short_message=b'Test message'
)
# Expected: Command status = ESME_ROK (0x00000000)
# DLR with stat=DELIVRD will be logged after delay

client.unbind()
client.disconnect()
```

### Run Unit Tests

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SMPP_HOST` | `0.0.0.0` | SMPP server bind address |
| `SMPP_PORT` | `2776` | SMPP server port |
| `SMPP_SYSTEM_ID` | `testuser` | Required system_id for authentication |
| `SMPP_PASSWORD` | `testpass` | Required password |
| `HLR_API_KEY` | - | **Required**: TMT Velocity API key |
| `HLR_API_SECRET` | - | **Required**: TMT Velocity API secret |
| `HLR_BASE_URL` | `https://api.tmtvelocity.com/live/json` | TMT API endpoint |
| `HLR_TIMEOUT_SECONDS` | `5.0` | HLR request timeout |
| `HLR_TIMEOUT_POLICY` | `reject` | Action on timeout: `reject` |
| `HLR_CACHE_TTL_SECONDS` | `86400` | Cache TTL (0 to disable) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `REDIS_MAX_CONNECTIONS` | `10` | Redis pool size |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format: `json` or `console` |
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics |
| `METRICS_PORT` | `9091` | Metrics HTTP port |
| `DLR_DELAY_SECONDS` | `1.0` | Delay before sending DELIVRD DLR |

### Behavior Logic

The gateway implements **reverse filtering**:

1. **SubmitSM received** → Start async HLR lookup
2. **HLR returns result:**
   - **Valid** (`error=0`, `status=0`, `present=yes`) → Return `ESME_RINVDSTADR` immediately (rejected)
   - **Invalid** (any other condition) → Return `ESME_ROK` with message_id, schedule DELIVRD DLR
3. **DLR sent** after `DLR_DELAY_SECONDS` with format:
   ```
   id:ABC123 sub:001 dlvrd:000 submit date:2510091430 done date:2510091431 stat:DELIVRD err:000 text:
   ```

### HLR Error Mapping

| TMT Error | SMPP DLR Error | Description |
|-----------|----------------|-------------|
| `1` (status=1) | `003`          | Invalid destination |
| `1` (present=no) | `001`          | Unknown subscriber |
| `2` | `002`          | Absent subscriber |
| `191` | `000`          | Unsupported network (portability) |
| `192` | `000`          | Unsupported network (origin) |
| `193` | `000`          | Landline/fixed network |

## 📊 Metrics

Prometheus metrics available at `http://localhost:9091/metrics`:

### Counters
- `submit_total{status="accepted|rejected"}` - Total SubmitSM requests
- `hlr_requests_total{result="valid|invalid|timeout|error"}` - HLR API requests by result
- `hlr_cache_hits_total` - Redis cache hits
- `hlr_cache_misses_total` - Redis cache misses
- `delivrd_total{reason="invalid_number|timeout|hlr_error"}` - DELIVRD DLRs sent

### Histograms
- `hlr_latency_seconds` - HLR API response time
- `submit_processing_seconds` - SubmitSM processing time

### Gauges
- `active_smpp_connections` - Current active SMPP connections
- `active_tasks` - Current asyncio tasks (DLR processing)
- `redis_connection_pool_size` - Redis pool size

## 📝 Logging

### JSON Format (Production)
```bash
LOG_FORMAT=json
```

Example output:
```json
{
  "event": "submit_sm_received",
  "message_id": "A1B2C3D4E5F6G7H8",
  "source": "1234",
  "destination": "13476841841",
  "message_length": 12,
  "timestamp": "2025-10-09T14:30:00.123Z",
  "level": "info"
}
```

### Console Format (Development)
```bash
LOG_FORMAT=console
```

Example output:
```
2025-10-09 14:30:00 [info     ] submit_sm_received message_id=A1B2C3D4E5F6G7H8 source=1234 destination=13476841841
```

## 🏥 Health Checks

### Container Health
```bash
# Docker health check
docker inspect smpp-gateway --format='{{.State.Health.Status}}'

# Manual check
docker exec smpp-gateway python main.py healthcheck
```

### Component Status
```bash
# Check SMPP port
nc -zv localhost 2776

# Check metrics endpoint
curl http://localhost:9091/metrics

# Check Redis
docker exec smpp-redis redis-cli ping
```

## 🔧 Troubleshooting

### SMPP Connection Issues

**Problem**: Client cannot connect to port 2776

```bash
# Check if port is listening
netstat -tlnp | grep 2776

# Check container logs
docker-compose logs smpp-gateway

# Check firewall
sudo ufw status
```

### Authentication Failures

**Problem**: Bind rejected with `ESME_RINVPASWD`

```bash
# Verify credentials in .env
cat .env | grep SMPP_

# Check logs for bind attempts
docker-compose logs smpp-gateway | grep bind
```

### HLR API Errors

**Problem**: Frequent HLR timeouts or errors

```bash
# Check HLR metrics
curl http://localhost:9091/metrics | grep hlr_requests_total

# Increase timeout
echo "HLR_TIMEOUT_SECONDS=10.0" >> .env
docker-compose restart smpp-gateway

# Check API credentials
curl "https://api.tmtvelocity.com/live/json/$HLR_API_KEY/$HLR_API_SECRET/13476841841"
```

### Redis Connection Issues

**Problem**: Cache not working

```bash
# Check Redis health
docker-compose ps redis

# Test Redis connection
docker exec smpp-redis redis-cli ping

# Check Redis logs
docker-compose logs redis

# Restart Redis
docker-compose restart redis
```

### High Memory Usage

**Problem**: Container consuming too much memory

```bash
# Check current usage
docker stats smpp-gateway

# Adjust cache TTL (reduce memory footprint)
echo "HLR_CACHE_TTL_SECONDS=3600" >> .env

# Adjust Redis max connections
echo "REDIS_MAX_CONNECTIONS=5" >> .env

# Restart
docker-compose restart smpp-gateway
```

## 📦 Project Structure

```
smpp_hlr_gateway/
├── src/
│   ├── __init__.py
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration management
│   ├── logging_config.py    # Structured logging setup
│   ├── metrics.py           # Prometheus metrics
│   ├── hlr/
│   │   ├── __init__.py
│   │   ├── client.py        # TMT Velocity HLR client
│   │   └── cache.py         # Redis cache layer
│   └── smpp/
│       ├── __init__.py
│       ├── server.py        # Async SMPP server
│       ├── handler.py       # SubmitSM processing logic
│       └── pdu_builder.py   # PDU and DLR builders
├── tests/
│   ├── conftest.py          # Pytest configuration
│   ├── test_hlr_client.py   # HLR client tests
│   ├── test_handler_logic.py # Handler logic tests
│   └── test_integration.py  # Integration tests
├── Dockerfile               # Container definition
├── docker-compose.yml       # Docker Compose config
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
├── .dockerignore           # Docker ignore rules
└── README.md               # This file
```

## 🧪 Example Scenarios

### Scenario 1: Block Valid Numbers

```python
# Valid US Verizon number
msisdn = "13476841841"

# HLR response:
{
  "error": 0,
  "status": 0,
  "present": "yes",
  "type": "mobile"
}

# Gateway action: Reject with ESME_RINVDSTADR
# No DLR sent
```

### Scenario 2: Accept Invalid Numbers

```python
# Invalid number
msisdn = "40722570240999"

# HLR response:
{
  "error": 1,
  "status": 1,
  "status_message": "Invalid Number"
}

# Gateway action:
# 1. Return SubmitSmResp OK with message_id
# 2. Wait DLR_DELAY_SECONDS
# 3. Send DeliverSM with DELIVRD (logged)
```

### Scenario 3: Unsupported Network

```python
# Nigerian number on unsupported network
msisdn = "2347010000044"

# HLR response:
{
  "error": 191,
  "present": "na",
  "ported": true
}

# Gateway action: Accept + DELIVRD
# DLR error code: 000 (Unknown subscriber)
```

### Scenario 4: Landline Number

```python
# French landline
msisdn = "33387840133"

# HLR response:
{
  "error": 193,
  "type": "fixed"
}

# Gateway action: Accept + DELIVRD
# DLR error code: 003 (Invalid destination)
```

## 🔐 Security Considerations

### Production Deployment

1. **Change default credentials**:
```bash
SMPP_SYSTEM_ID=prod_user_$(openssl rand -hex 8)
SMPP_PASSWORD=$(openssl rand -base64 32)
```

2. **Use secrets management**:
```bash
# Docker secrets
docker secret create hlr_api_key /path/to/key
docker secret create hlr_api_secret /path/to/secret
```

3. **Restrict network access**:
```yaml
# docker-compose.yml
networks:
  smpp-network:
    internal: true  # No external access
```

4. **Enable TLS** (if supported by your SMPP stack)

5. **Rate limiting** (implement in reverse proxy like nginx)

## 🚀 Performance Tuning

### High-Throughput Configuration

```bash
# Increase timeouts for busy networks
HLR_TIMEOUT_SECONDS=10.0

# Larger Redis pool
REDIS_MAX_CONNECTIONS=50

# Longer cache TTL (reduce API calls)
HLR_CACHE_TTL_SECONDS=604800  # 7 days

# Reduce DLR delay for faster processing
DLR_DELAY_SECONDS=0.1
```

### Resource Limits

```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 2G
    reservations:
      cpus: '1'
      memory: 512M
```

## 📄 Example DLR Output

```
id:F3A7B9C1D2E45678 sub:001 dlvrd:000 submit date:2510091430 done date:2510091431 stat:DELIVRD err:000 text:
```

Fields:
- `id`: Original message ID
- `sub`: Submitted (always 001)
- `dlvrd`: Delivered (always 000 for DELIVRD)
- `submit date`: When message was received (YYMMDDhhmm)
- `done date`: When DLR was generated (YYMMDDhhmm)
- `stat`: Delivery status (`DELIVRD`)
- `err`: Error code (`001`=Unknown subscriber, `003`=Invalid destination)
- `text`: Empty for standard DLR

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/ -v`
5. Submit a pull request

## 📜 License

MIT License - see LICENSE file for details

## 🐛 Known Limitations

1. **DeliverSM not fully implemented**: Currently DLRs are only logged, not sent via SMPP (requires receiver binding)
2. **Single system_id**: Only one authentication credential supported
3. **No TLS support**: Plain TCP only (add nginx/stunnel for TLS)
4. **Limited SMPP features**: Only SubmitSM/SubmitSmResp implemented

## 🔗 Resources

- [TMT Velocity API Docs](https://www.tmtvelocity.com/)
- [SMPP v3.4 Specification](https://smpp.org/SMPP_v3_4_Issue1_2.pdf)
- [python-smpplib](https://github.com/python-smpplib/python-smpplib)
- [Prometheus Python Client](https://github.com/prometheus/client_python)

## 💬 Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/smpp_hlr_gateway/issues)
- Email: support@example.com

---

**Built with ❤️ using Python 3.11+, asyncio, and modern async libraries**