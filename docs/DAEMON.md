# Fullon Master API - Daemon Mode

Complete guide to running Fullon Master API as a background daemon process.

## Overview

The `start_fullon.py` script provides full daemon lifecycle management, allowing the API to run as a background process with proper PID tracking, logging, and signal handling.

## Quick Start

```bash
# Start daemon
./start_fullon.py start

# Check status
./start_fullon.py status

# Stop daemon
./start_fullon.py stop
```

## Daemon Commands

### Start

```bash
./start_fullon.py start
```

**What it does:**
- Forks process to run in background
- Detaches from terminal session
- Creates PID file at `~/.fullon_master_api.pid`
- Redirects logs to `/tmp/fullon_master_api.log`
- Starts uvicorn server with configured settings

**Output:**
```
🚀 Starting fullon_master_api daemon...
✅ Daemon started with PID 12345
   Log file: /tmp/fullon_master_api.log
   PID file: /home/user/.fullon_master_api.pid

   Check status: ./start_fullon.py status
   View logs:    ./start_fullon.py logs
```

### Stop

```bash
./start_fullon.py stop
```

**What it does:**
- Sends SIGTERM signal for graceful shutdown
- Waits up to 10 seconds for process to stop
- Force kills (SIGKILL) if not stopped gracefully
- Removes PID file

**Output:**
```
⏹️  Stopping fullon_master_api daemon (PID 12345)...
..........
✅ Daemon stopped
```

### Restart

```bash
./start_fullon.py restart
```

**What it does:**
- Stops the daemon (if running)
- Waits 2 seconds
- Starts the daemon again

Equivalent to: `./start_fullon.py stop && sleep 2 && ./start_fullon.py start`

### Status

```bash
./start_fullon.py status
```

**What it does:**
- Checks if PID file exists
- Verifies process is actually running
- Shows server URLs and configuration

**Output:**
```
============================================================
fullon_master_api Daemon Status
============================================================
Status:   ✅ Running
PID:      12345
PID File: /home/user/.fullon_master_api.pid
Log File: /tmp/fullon_master_api.log

Server:   http://0.0.0.0:8000
Docs:     http://0.0.0.0:8000/docs
Health:   http://0.0.0.0:8000/health
============================================================
```

### Logs

```bash
# Tail logs (follow mode)
./start_fullon.py logs

# Show last 50 lines (no follow)
./start_fullon.py logs --no-follow

# Show last 100 lines
./start_fullon.py logs --no-follow --lines 100
```

**What it does:**
- Displays daemon log file
- Default: tail -f (follows new log entries)
- Can show specific number of lines

## Using Makefile

Convenience commands via Makefile:

```bash
make daemon-start    # Start daemon
make daemon-stop     # Stop daemon
make daemon-restart  # Restart daemon
make daemon-status   # Check status
make daemon-logs     # Tail logs
```

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| PID File | `~/.fullon_master_api.pid` | Stores daemon PID |
| Log File | `/tmp/fullon_master_api.log` | Daemon logs (stdout/stderr) |
| Script | `./start_fullon.py` | Daemon control script |

## Environment Configuration

Daemon reads configuration from `.env` file:

```bash
# Server settings
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Database
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=fullon2

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT
JWT_SECRET_KEY=your-secret-key
```

## Signal Handling

The daemon properly handles Unix signals:

| Signal | Behavior |
|--------|----------|
| SIGTERM | Graceful shutdown (removes PID file, stops server) |
| SIGINT | Graceful shutdown (same as SIGTERM) |
| SIGKILL | Force kill (PID file must be manually removed) |

## Systemd Integration

For production deployments, use systemd instead of manual daemon control:

### Installation

```bash
# Copy service file
sudo cp fullon_master_api.service /etc/systemd/system/

# Edit paths in service file
sudo vim /etc/systemd/system/fullon_master_api.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable fullon_master_api

# Start service
sudo systemctl start fullon_master_api
```

### Systemd Commands

```bash
# Start
sudo systemctl start fullon_master_api

# Stop
sudo systemctl stop fullon_master_api

# Restart
sudo systemctl restart fullon_master_api

# Status
sudo systemctl status fullon_master_api

# Logs
sudo journalctl -u fullon_master_api -f

# Enable auto-start on boot
sudo systemctl enable fullon_master_api

# Disable auto-start
sudo systemctl disable fullon_master_api
```

## Troubleshooting

### Daemon Won't Start

```bash
# Check if already running
./start_fullon.py status

# Check port availability
lsof -i :8000

# Check logs for errors
./start_fullon.py logs --no-follow --lines 50
```

### Stale PID File

If daemon crashed and PID file wasn't removed:

```bash
# Remove stale PID file
rm ~/.fullon_master_api.pid

# Start daemon again
./start_fullon.py start
```

### Permission Errors

```bash
# Make script executable
chmod +x start_fullon.py

# Check log directory permissions
ls -la /tmp/fullon_master_api.log
```

### Can't Connect to API

```bash
# Check if daemon is running
./start_fullon.py status

# Check logs for errors
./start_fullon.py logs --no-follow --lines 100

# Test health endpoint
curl http://localhost:8000/health

# Check firewall rules
sudo ufw status
```

## Development vs Production

### Development Mode

```bash
# Use foreground server with auto-reload
make run

# OR use Poetry directly
poetry run uvicorn fullon_master_api.main:app --reload
```

**Features:**
- Auto-reload on code changes
- Detailed logging to console
- Easy to stop (Ctrl+C)
- Easier debugging

### Production Mode

```bash
# Use daemon mode
./start_fullon.py start

# OR use systemd
sudo systemctl start fullon_master_api
```

**Features:**
- Runs in background
- Survives terminal disconnection
- Automatic restart on failure (systemd)
- Log rotation (systemd)
- Starts on system boot (systemd)

## Example: Daemon Lifecycle

```bash
# 1. Start daemon
./start_fullon.py start
# Output: ✅ Daemon started with PID 12345

# 2. Verify it's running
./start_fullon.py status
# Output: Status: ✅ Running, PID: 12345

# 3. Check API health
curl http://localhost:8000/health
# Output: {"status":"healthy","version":"1.0.0","service":"fullon_master_api"}

# 4. View logs
./start_fullon.py logs --no-follow --lines 20

# 5. Restart daemon
./start_fullon.py restart
# Output: 🔄 Restarting fullon_master_api daemon...

# 6. Stop daemon
./start_fullon.py stop
# Output: ✅ Daemon stopped
```

## Programmatic Control

Use `example_daemon_control.py` for programmatic daemon management:

```bash
# Start via example
python examples/example_daemon_control.py --action start

# Check status
python examples/example_daemon_control.py --action status

# View logs
python examples/example_daemon_control.py --action logs --lines 50

# Full lifecycle demo
python examples/example_daemon_control.py --action lifecycle
```

## Best Practices

1. **Always check status before start** - Prevents multiple instances
2. **Use systemd in production** - Better process management and monitoring
3. **Monitor logs regularly** - `./start_fullon.py logs` or `journalctl`
4. **Graceful shutdowns** - Use `stop` command, not `kill -9`
5. **Set proper environment variables** - Configure via `.env` file
6. **Log rotation** - Use systemd or logrotate for log management
7. **Health monitoring** - Regularly check `/health` endpoint

## Security Considerations

1. **PID File Location** - `~/.fullon_master_api.pid` is user-specific
2. **Log File Permissions** - `/tmp` is world-writable, consider `/var/log/fullon/`
3. **Process User** - Run as dedicated user (not root) in production
4. **Systemd Security** - Service file includes security hardening options

## See Also

- [README.md](README.md) - Main documentation
- [masterplan.md](masterplan.md) - Architecture and implementation plan
- [examples/example_daemon_control.py](examples/example_daemon_control.py) - Programmatic daemon control
- [fullon_master_api.service](fullon_master_api.service) - Systemd service file
