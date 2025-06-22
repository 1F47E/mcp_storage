# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an MCP (Model Context Protocol) Server implementation in Go that provides database connectivity tools for LLMs. It implements pure HTTP transport (no SSE) following the MCP specification version 2024-11-05, allowing LLMs to interact with PostgreSQL and MySQL databases.

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
DEBUG=1 ./mcp-storage

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
Database connections are configured in `config.yaml`. The server reads this file to establish connections to PostgreSQL and MySQL databases.

## Key Development Notes

1. **Database Operations**: Supports full database operations for PostgreSQL and MySQL
2. **Dual Implementation**: When modifying functionality, consider both Python and Go implementations
3. **Transport**: HTTP transport only, accessible via localhost:5435
4. **Port Configuration**: Default HTTP port is 5435
5. **Virtual Environment**: Always use `.venv` for Python dependencies, not global installation
6. **Docker Usage**: Server runs in Docker container, accessible at localhost:5435

## Testing Approach
No formal test suite exists. Use the included client for manual testing:
```bash
# List available tools
uv run client --transport http --port 5435

# Test specific tool
uv run client --transport http --port 5435 --tool postgres_schemas
```

## Integration Notes
This server is designed for Claude Code and Cursor AI integration via MCP. It runs locally in a Docker container and exposes database tools through the MCP protocol over HTTP, allowing AI assistants to query databases directly through the chat interface.

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# Check server health
curl http://localhost:5435/health

# View logs
docker-compose logs -f mcp-storage
```