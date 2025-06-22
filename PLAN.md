# Go Implementation Plan for mcp-storage

## Overview

This plan outlines the conversion of mcp-storage from Python to Go, using Fiber framework and an adapter pattern for database support.

## Architecture

### Core Principles
1. **Adapter Pattern**: Database implementations are pluggable adapters
2. **Environment-based Configuration**: Use .env file instead of config.yaml
3. **Fail-fast**: Panic on startup if no adapters are configured
4. **Extensible**: Easy to add new database adapters (Redis, MongoDB, etc.)

### File Structure (Flat and Simple)
```
/mcp-storage/ (go branch)
├── main.go              # Entry point
├── config.go            # Environment config loader
├── adapter.go           # Database adapter interface
├── postgres.go          # PostgreSQL adapter implementation
├── mysql.go             # MySQL adapter implementation
├── tools.go             # MCP tool implementations
├── transport.go         # HTTP transport & OAuth endpoints
├── .env.example         # Example environment file
├── go.mod
├── go.sum
├── Dockerfile
└── docker-compose.yml
```

## Environment Configuration

### Environment Variables
```bash
# Server Configuration
PORT=5435
HOST=0.0.0.0
LOG_LEVEL=info

# PostgreSQL Adapter (if set, enables PostgreSQL)
POSTGRES_URL=postgresql://user:password@localhost:5432/dbname?sslmode=disable

# MySQL Adapter (if set, enables MySQL)
MYSQL_DSN=user:password@tcp(localhost:3306)/dbname?charset=utf8mb4&parseTime=True

# Future adapters
# REDIS_URL=redis://localhost:6379/0
# MONGODB_URI=mongodb://localhost:27017/dbname
```

## Adapter Interface

```go
type DatabaseAdapter interface {
    Name() string
    Connect() error
    Close() error
    IsEnabled() bool
    
    // Schema operations
    ListSchemas() ([]Schema, error)
    GetSchemaDDL(schemaName string) (string, error)
    
    // Query operations
    ExecuteSelect(query string) (QueryResult, error)
}

type AdapterRegistry struct {
    adapters map[string]DatabaseAdapter
}
```

## Implementation Details

### 1. Config Loader (config.go)
- Load environment variables using godotenv
- Validate that at least one adapter is configured
- Panic if no adapters are available

### 2. Main Entry Point (main.go)
- Load configuration
- Initialize adapter registry
- Register enabled adapters based on environment
- Setup MCP server with tools
- Start Fiber HTTP server

### 3. Database Adapters (postgres.go, mysql.go)
- Implement DatabaseAdapter interface
- Handle connection pooling
- Provide schema introspection
- Execute SELECT queries safely

### 4. HTTP Transport (transport.go)
- Main MCP endpoint: `POST /`
- Health check: `GET /health`
- OAuth mock endpoints for Claude Code compatibility:
  - `GET /.well-known/oauth-authorization-server`
  - `POST /register`
  - `GET /authorize`
  - `POST /token`

### 5. MCP Tools (tools.go)
- `random_uint64` - Generate random number (always available)
- PostgreSQL tools (if adapter enabled):
  - `postgres_schemas` - List schemas
  - `postgres_schema_ddls` - Get DDL statements
  - `postgres_query_select` - Execute SELECT queries
- MySQL tools (if adapter enabled):
  - `mysql_query_select` - Execute SELECT queries
  - `mysql_schema_ddls` - Get DDL statements

## Docker Configuration

### Dockerfile (Multi-stage build)
```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.* ./
RUN go mod download
COPY *.go ./
RUN go build -o mcp-storage

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/mcp-storage .
COPY .env* ./
EXPOSE 5435
CMD ["./mcp-storage"]
```

### docker-compose.yml
```yaml
services:
  mcp-storage:
    build: .
    container_name: mcp-storage-go
    ports:
      - "5435:5435"
    env_file:
      - .env
    environment:
      - PORT=5435
      - HOST=0.0.0.0
    restart: unless-stopped
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
```

## Key Features

1. **StreamableHTTP Transport**: Compatible with Claude Code and other MCP clients
2. **Concurrent Handling**: Leverage Go's goroutines for multiple database operations
3. **Type Safety**: Strong typing for all request/response structures
4. **Error Handling**: Proper error propagation and logging
5. **Graceful Shutdown**: Clean connection closing on termination

## Testing Strategy

1. Unit tests for each adapter
2. Integration tests with test databases
3. Mock OAuth flow testing
4. Performance benchmarks
5. Docker container testing

## Migration Path

1. ✅ Create `go` branch
2. ✅ Create project structure and planning documents
3. Implement core files in order:
   - config.go (environment loader)
   - adapter.go (interface definition)
   - postgres.go (PostgreSQL adapter)
   - mysql.go (MySQL adapter)
   - tools.go (MCP tool implementations)
   - transport.go (HTTP endpoints)
   - main.go (entry point)
4. Create Dockerfile
5. Update docker-compose.yml
6. Test with various configurations
7. Document usage in README

## Future Extensions

The adapter pattern makes it easy to add:
- Redis adapter for key-value operations
- MongoDB adapter for document queries
- SQLite adapter for local development
- ClickHouse adapter for analytics
- Any other database with a Go driver