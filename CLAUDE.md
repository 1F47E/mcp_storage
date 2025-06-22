# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an MCP (Model Context Protocol) Server implementation that provides database connectivity tools for LLMs. It has both Python and Go implementations of the same protocol, allowing LLMs to interact with PostgreSQL and MySQL databases.

## Development Commands

### Python Server
```bash
# Activate virtual environment first
source .venv/bin/activate  # or create with: python -m venv .venv

# Install dependencies
uv pip install -e .

# Run server with HTTP transport (default port 5435)
make server
# or directly:
uv run mcp-storage --transport http --port 5435

# Run test client
make client
# or directly:
uv run client --transport http --port 5435
```

### Go Server
```bash
# Run Go server
go run server.go

# Build Go server
go build server.go
```

### Docker
```bash
# Build and run with Docker
docker-compose up
```

## Architecture

### Core Components
1. **Python Implementation** (`mcp_server/`): Main server using MCP SDK, asyncio, and database drivers
2. **Go Implementation** (`server.go`): Alternative server using Fiber v2 and mark3labs/mcp-go
3. **Transport Layer**: HTTP (Streamable HTTP) for communication via localhost:5435
4. **Database Connectivity**: PostgreSQL (psycopg2) and MySQL (PyMySQL) with database operations

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