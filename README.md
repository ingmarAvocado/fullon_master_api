# Fullon Master API

**Unified API Gateway for the Fullon Trading Platform**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

Fullon Master API is a unified API gateway that composes existing Fullon microservices with centralized JWT authentication. It follows the **LRRS principles** (Little, Responsible, Reusable, Separate) and provides a single entry point for all Fullon trading operations.

## Features

- 🔐 **Centralized JWT Authentication** - Single auth layer for all downstream APIs
- 🔄 **Router Composition** - Composes existing APIs without code duplication
- 🌐 **WebSocket Support** - Real-time data streaming via proxied connections
- 📊 **Unified Health Monitoring** - Aggregate status across all subsystems
- 🚀 **Production Ready** - Built on FastAPI with async/await patterns

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    fullon_master_api                        │
│                  (Unified API Gateway)                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         JWT Authentication Middleware                │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│     ┌────────────────────┼────────────────────┐            │
│     ▼                    ▼                    ▼            │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐         │
│  │   ORM    │      │  OHLCV   │      │  Cache   │         │
│  │ Routers  │      │ Routers  │      │WebSocket │         │
│  └──────────┘      └──────────┘      └──────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.13+
- Poetry
- PostgreSQL (for fullon_orm)
- Redis (for fullon_cache)

### Installation

```bash
# Clone repository
git clone https://github.com/ingmarAvocado/fullon_master_api.git
cd fullon_master_api

# Setup project
make setup

# Update .env with your credentials
vim .env

# Run development server (foreground)
make run

# OR run as daemon (background)
make daemon-start
```

The API will be available at `http://localhost:8000`

### Running as Daemon

The API can run as a background daemon process:

```bash
# Start daemon
./start_fullon.py start
# or
make daemon-start

# Check status
./start_fullon.py status
# or
make daemon-status

# View logs
./start_fullon.py logs
# or
make daemon-logs

# Stop daemon
./start_fullon.py stop
# or
make daemon-stop

# Restart daemon
./start_fullon.py restart
# or
make daemon-restart
```

**Daemon features:**
- Runs in background as forked process
- PID file: `~/.fullon_master_api.pid`
- Log file: `/tmp/fullon_master_api.log`
- Graceful shutdown (SIGTERM handling)
- Systemd service file included

### Development

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Format code
make format

# Run linters
make lint
```

### Examples-Driven Issue Workflow

This project uses an **examples-driven, test-driven development** workflow:

```
masterplan.md → issue manifest → GitHub issues → test stubs → TDD → passing tests
```

**Key principles:**
- ✅ **Examples define WHAT** - Executable contracts showing expected behavior
- ✅ **Tests define HOW we validate** - pytest tests that must pass
- ✅ **Issues define incremental steps** - One function/method per issue
- ✅ **GitHub tracks progress** - Issues, labels, dependencies

**Workflow:**

```bash
# 1. Generate GitHub issues from manifest
python scripts/generate_phase_issues.py --phase 2

# 2. Create test stubs
python scripts/create_test_stubs.py --phase 2

# 3. View issues
gh issue list --label phase-2-jwt

# 4. Pick an issue and implement using TDD
# - Remove pytest.skip() from test
# - Run test (should fail)
# - Implement code
# - Run test (should pass)
# - Close issue

# 5. Track progress
poetry run pytest -v
```

See [ISSUES_WORKFLOW.md](ISSUES_WORKFLOW.md) for complete workflow documentation.

## API Documentation

Once the server is running, visit:

- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Project Structure

```
fullon_master_api/
├── src/fullon_master_api/
│   ├── __init__.py           # Library exports
│   ├── main.py               # FastAPI app entry point
│   ├── gateway.py            # MasterGateway class
│   ├── config.py             # Environment configuration
│   ├── auth/                 # Authentication (Phase 2)
│   ├── routers/              # Custom routers (Phase 6)
│   └── websocket/            # WebSocket utilities (Phase 5)
├── tests/                    # Test suite
├── examples/                 # Usage examples
├── docs/                     # Component documentation
├── pyproject.toml            # Poetry dependencies
├── Makefile                  # Development commands
└── README.md                 # This file
```

## Configuration

All configuration is via environment variables (`.env` file):

```env
# JWT Authentication
JWT_SECRET_KEY=your-secret-key-here

# Database (fullon_orm)
DB_USER=postgres
DB_PASSWORD=your-password
DB_NAME=fullon2

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
```

See `.env.example` for complete configuration options.

## Development Roadmap

**Phase 1**: ✅ Project Foundation (Current)
**Phase 2**: JWT Authentication
**Phase 3**: ORM Router Composition
**Phase 4**: OHLCV Router Composition
**Phase 5**: Cache WebSocket Proxy
**Phase 6**: Health & Monitoring
**Phase 7**: Integration Testing
**Phase 8**: Documentation & ADRs

See [masterplan.md](masterplan.md) for detailed implementation plan.

## Contributing

This project follows examples-driven development and LRRS principles. See [CLAUDE.md](CLAUDE.md) for LLM development guide.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Related Projects

- [fullon_orm](https://github.com/ingmarAvocado/fullon_orm) - Database ORM layer
- [fullon_cache](https://github.com/ingmarAvocado/fullon_cache) - Redis caching
- [fullon_ohlcv](https://github.com/ingmarAvocado/fullon_ohlcv) - Market data
- [fullon_log](https://github.com/ingmarAvocado/fullon_log) - Logging utilities
