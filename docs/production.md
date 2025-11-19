# Production Deployment Guide

This guide covers production configuration for EchoAI, with focus on WebSocket keepalive settings and infrastructure timeouts.

## WebSocket Keepalive Configuration

EchoAI implements application-level keepalive (ping/pong) and idle monitoring to maintain stable WebSocket connections during long meetings.

### Configuration Constants

Located in `backend/app/routers/meeting.py`:

```python
KEEPALIVE_INTERVAL = 20  # Send ping every 20 seconds
MAX_IDLE = 30 * 60       # Close connection after 30 minutes of inactivity
```

### How It Works

1. **Keepalive Sender**: Automatically sends JSON ping messages every `KEEPALIVE_INTERVAL` seconds
   ```json
   {"type": "ping", "ts": 1234567890.123, "timestamp": "2024-01-01T12:00:00.000Z"}
   ```

2. **Idle Monitor**: Tracks the last received message timestamp and closes the connection after `MAX_IDLE` seconds of no incoming messages

3. **Client Pong**: Clients should respond to server pings with:
   ```json
   {"type": "pong", "timestamp": "2024-01-01T12:00:00.000Z"}
   ```

### Tuning Guidelines

#### KEEPALIVE_INTERVAL

- **Default**: 20 seconds (safe for most deployments)
- **Recommendation**: Set to less than the shortest proxy/load balancer idle timeout in your infrastructure
- **Examples**:
  - Behind AWS ALB (60s idle timeout): Use 30s or less
  - Behind Cloudflare (100s idle timeout): Use 50s or less
  - Behind nginx with 300s timeout: Use 120s or less
- **Trade-offs**:
  - Lower values: More network overhead, better connection health detection
  - Higher values: Less network overhead, risk of proxy timeouts

#### MAX_IDLE

- **Default**: 1800 seconds (30 minutes)
- **Recommendation**: Set based on your meeting duration requirements
- **Examples**:
  - Short meetings (< 15 min): 900s (15 minutes)
  - Standard meetings (30-60 min): 1800s (30 minutes)
  - Long meetings (60+ min): 3600s (60 minutes)
- **Trade-offs**:
  - Lower values: Free up resources faster, may disconnect during silence
  - Higher values: Support longer meetings, hold resources longer

## Uvicorn Configuration

Configure uvicorn to support long-lived WebSocket connections:

### Recommended Settings

```bash
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --timeout-keep-alive 1800 \
  --timeout-graceful-shutdown 10 \
  --workers 1
```

### Configuration Explanation

- `--timeout-keep-alive 1800`: HTTP keepalive timeout (30 minutes)
  - Should be ≥ MAX_IDLE
  - Prevents uvicorn from closing idle connections prematurely
  
- `--timeout-graceful-shutdown 10`: Graceful shutdown timeout
  - Allows in-flight requests to complete
  - WebSocket connections are notified and closed cleanly

- `--workers 1`: Single worker process
  - WebSocket connections are stateful and tied to a specific worker
  - Use 1 worker or implement sticky sessions with a load balancer
  - For multi-worker setups, use Redis or similar for session state

### Environment-Specific Configuration

**Development:**
```bash
uvicorn app.main:app --reload --timeout-keep-alive 300
```

**Staging:**
```bash
uvicorn app.main:app --timeout-keep-alive 1800 --workers 1
```

**Production:**
```bash
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --timeout-keep-alive 1800 \
  --workers 1 \
  --log-level info
```

## Nginx Reverse Proxy Configuration

When deploying behind nginx, configure appropriate timeouts:

### Recommended Configuration

```nginx
upstream echoai_backend {
    server localhost:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    # WebSocket-specific location
    location /meeting/rooms/ {
        proxy_pass http://echoai_backend;
        
        # WebSocket upgrade headers
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Essential headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # ⚠️ IMPORTANT: WebSocket timeout configuration
        # Should be > MAX_IDLE to prevent premature disconnection
        proxy_read_timeout 1800s;    # 30 minutes
        proxy_send_timeout 1800s;    # 30 minutes
        proxy_connect_timeout 60s;   # Connection establishment timeout
        
        # Keep connection alive between nginx and upstream
        proxy_socket_keepalive on;
        keepalive_timeout 1800s;
    }
    
    # Regular HTTP location (API endpoints)
    location / {
        proxy_pass http://echoai_backend;
        proxy_http_version 1.1;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Shorter timeouts for regular HTTP
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
        proxy_connect_timeout 10s;
    }
}
```

### Nginx Timeout Explanation

- `proxy_read_timeout 1800s`: Maximum time between successive read operations
  - **MUST be ≥ MAX_IDLE** (or connections will be closed prematurely)
  - Set to at least your expected meeting duration
  
- `proxy_send_timeout 1800s`: Maximum time between successive write operations
  - Should match proxy_read_timeout
  
- `keepalive_timeout 1800s`: How long to keep idle connections open
  - Should match your WebSocket keepalive requirements

### SSL/TLS Configuration (wss://)

For secure WebSocket connections (recommended for production):

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # WebSocket location with same timeout configuration
    location /meeting/rooms/ {
        proxy_pass http://echoai_backend;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        proxy_read_timeout 1800s;
        proxy_send_timeout 1800s;
        proxy_connect_timeout 60s;
        
        proxy_socket_keepalive on;
        keepalive_timeout 1800s;
    }
    
    # Redirect HTTP API to regular location
    location / {
        proxy_pass http://echoai_backend;
        # ... other settings
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

## Cloud Provider Considerations

### AWS Application Load Balancer (ALB)

- **Default idle timeout**: 60 seconds
- **Configuration**: Increase to at least `MAX_IDLE` + buffer
  ```bash
  aws elbv2 modify-load-balancer-attributes \
    --load-balancer-arn <arn> \
    --attributes Key=idle_timeout.timeout_seconds,Value=1900
  ```

### Google Cloud Load Balancer

- **Default timeout**: 30 seconds (HTTP/S), 10 minutes (TCP)
- **Recommendation**: Use TCP load balancer for WebSockets or configure backend service timeout
  ```bash
  gcloud compute backend-services update <service-name> \
    --timeout=1800s
  ```

### Azure Application Gateway

- **Default timeout**: 30 seconds
- **Configuration**: Set connection idle timeout in portal or CLI
  ```bash
  az network application-gateway update \
    --name <gateway-name> \
    --resource-group <rg> \
    --set backendHttpSettingsCollection[0].requestTimeout=1800
  ```

## Monitoring and Debugging

### Log Messages

The keepalive implementation logs useful information:

```
Starting keepalive sender with interval=20s
Starting idle monitor with max_idle=1800s
Sent keepalive ping
Idle check: 45.2s / 1800s
Connection idle for 1801.5s, closing (max=1800s)
Keepalive sender stopped
Idle monitor stopped
```

### Metrics to Monitor

1. **WebSocket connection duration**: Track how long connections stay open
2. **Keepalive failures**: Count failed ping sends (indicates network issues)
3. **Idle timeouts**: Count connections closed due to idle timeout
4. **Active connections**: Current number of WebSocket connections

### Troubleshooting

**Problem**: Connections close unexpectedly before MAX_IDLE

**Solution**: Check that all proxy/LB timeouts are greater than MAX_IDLE:
```bash
# Check nginx config
grep -r "timeout" /etc/nginx/
# Should show values > 1800s for WebSocket locations

# Check uvicorn timeout
ps aux | grep uvicorn | grep timeout-keep-alive
# Should show >= 1800
```

**Problem**: High network traffic from keepalive pings

**Solution**: Increase KEEPALIVE_INTERVAL (but keep it below proxy timeouts):
```python
KEEPALIVE_INTERVAL = 30  # Increase from 20 to 30 seconds
```

**Problem**: Connections stay open too long after clients disconnect

**Solution**: Decrease MAX_IDLE or implement additional health checks:
```python
MAX_IDLE = 15 * 60  # Decrease from 30 to 15 minutes
```

## Summary

For a standard EchoAI production deployment with 30-minute meeting support:

1. **Application** (`meeting.py`):
   - `KEEPALIVE_INTERVAL = 20` seconds
   - `MAX_IDLE = 1800` seconds (30 minutes)

2. **Uvicorn**:
   - `--timeout-keep-alive 1800`

3. **Nginx**:
   - `proxy_read_timeout 1800s`
   - `proxy_send_timeout 1800s`
   - `keepalive_timeout 1800s`

4. **Load Balancer**:
   - Idle timeout ≥ 1900 seconds (31+ minutes)

This configuration ensures stable WebSocket connections for meetings up to 30 minutes, with automatic cleanup of idle connections and graceful handling of network issues.
