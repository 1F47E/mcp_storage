# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an MCP (Model Context Protocol) Server implementation in Go that provides database connectivity tools for LLMs. It implements pure HTTP transport (no SSE) following the MCP specification version 2025-03-26, allowing LLMs to interact with PostgreSQL and MySQL databases.

## Development Commands

### Build and Run
```bash
# Build the server
make build

# Run locally
make run

# Run with debug logging
make run-debug
# or
LOG_LEVEL=debug ./mcp-storage

# Run with Docker
docker-compose up -d
```

### Testing
```bash
# Run tests with Python client
make test-mcp

# Test with debug output
make test-mcp-debug

# Test specific tool
python3 test_client.py --tool postgres_schemas --args '{"schema_name": "public"}'
```

### Development
```bash
# Run linters
make lint

# Clean build artifacts
make clean

# View Docker logs
docker-compose logs -f mcp-storage
```

### Docker
```bash
# Build and run with Docker
docker-compose up
```

## Architecture

### Core Components
1. **Go Implementation**: Pure Go server using Fiber v2 web framework
2. **Transport Layer**: HTTP POST for all MCP protocol communication (no SSE)
3. **Database Connectivity**: PostgreSQL and MySQL adapters with connection pooling
4. **Protocol Implementation**: Custom JSON-RPC handler following MCP specification

### Available Tools
- `random_uint64`: Generate random numbers
- `postgres_schemas`: List PostgreSQL schemas
- `postgres_schema_ddls`: Get PostgreSQL DDL statements
- `postgres_query_select`: Execute PostgreSQL SELECT queries
- `mysql_query_select`: Execute MySQL SELECT queries
- `mysql_schema_ddls`: Get MySQL DDL statements

### Configuration
Database connections are configured via environment variables. Create a `.env` file based on `.env.example`:
```bash
# Server Configuration
PORT=5435
HOST=0.0.0.0
LOG_LEVEL=info  # Options: trace, debug, info, warn, error

# PostgreSQL (optional)
POSTGRES_URL=postgresql://user:password@localhost:5432/dbname?sslmode=disable

# MySQL (optional) 
MYSQL_URL=user:password@tcp(localhost:3306)/dbname?charset=utf8mb4&parseTime=True
```

For Docker, use `.env.docker` with `host.docker.internal` for accessing host databases from container.

## Key Development Notes

1. **Protocol Version**: Server implements MCP protocol version `2025-03-26` (required by Claude CLI)
2. **Database Operations**: Supports read-only operations for PostgreSQL and MySQL (SELECT queries only)
3. **Transport**: Pure HTTP POST transport, no SSE (Server-Sent Events)
4. **Port Configuration**: Default HTTP port is 5435
5. **Docker Networking**: On macOS, use `host.docker.internal` to access host databases from Docker
6. **Debug Logging**: Set `LOG_LEVEL=debug` to see detailed request/response logs
7. **OAuth Mock**: Includes mock OAuth endpoints for Claude Code compatibility

## Testing Approach
Use the included Python test client for testing:
```bash
# Run all tests
python3 test_client.py

# Test specific tool
python3 test_client.py --tool postgres_schemas

# Test with arguments
python3 test_client.py --tool postgres_query_select --args '{"query": "SELECT version()"}'
```

## Integration Notes
This server is designed for Claude Code and Cursor AI integration via MCP. It runs locally and exposes database tools through the MCP protocol over HTTP.

### Claude CLI Integration
```bash
# Add server to Claude
claude mcp add --transport http mcp-storage http://localhost:5435

# Remove server
claude mcp remove mcp-storage

# List servers
claude mcp list
```

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# Check server health
curl http://localhost:5435/health

# View logs
docker-compose logs -f mcp-storage

# Restart server
docker-compose restart
```

## Implementation Details

### File Structure
- `main.go` - Entry point and MCP method registration
- `protocol.go` - MCP protocol types and constants
- `jsonrpc.go` - JSON-RPC 2.0 handler implementation
- `transport.go` - HTTP transport layer
- `adapter.go` - Database adapter interface
- `postgres.go` - PostgreSQL adapter implementation
- `mysql.go` - MySQL adapter implementation
- `tools.go` - MCP tool implementations
- `session.go` - Optional session management
- `logger.go` - Logging configuration
- `config.go` - Environment configuration loader
- `test_client.py` - Python test client

### Recent Changes
- Implemented full Go server from scratch (removed mark3labs/mcp-go dependency)
- Updated protocol version to 2025-03-26 for Claude CLI compatibility
- Added comprehensive debug logging for request/response tracking
- Fixed Docker networking for macOS host database access
- Removed Python implementation in favor of Go