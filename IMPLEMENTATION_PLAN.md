# MCP HTTP Streaming Server Implementation Plan

## Overview
Build a custom MCP server with HTTP streaming transport following the official MCP specification, removing mark3labs/mcp-go dependency.

## 1. Core Protocol Implementation

### 1.1 Create `protocol.go` - MCP Protocol Types
- JSON-RPC 2.0 message structures (Request, Response, Notification, Error)
- MCP-specific types (Initialize, Tool, Resource, etc.)
- Protocol version constant: "2024-11-05"

### 1.2 Create `jsonrpc.go` - JSON-RPC Handler
- Request parsing and validation
- Response formatting
- Error handling with proper JSON-RPC error codes
- Request ID tracking

## 2. HTTP Streaming Transport (NO SSE)

### 2.1 Update `transport.go` - Pure HTTP Streaming Implementation
- POST endpoint for all client-server communication
- NO Server-Sent Events (SSE) - deprecated in favor of pure HTTP
- Request-response pattern with JSON-RPC over HTTP POST
- Session management with `Mcp-Session-Id` header
- Stateless server operation (optional session storage)

### 2.2 Session Management (Optional)
- Generate secure session IDs (UUID) if needed
- Server decides whether to maintain session state
- Support for completely stateless operation

## 3. MCP Server Implementation

### 3.1 Update `main.go` - Server Entry Point
- Initialize Fiber app with proper middleware
- Setup HTTP routes (POST / and GET /)
- Graceful shutdown handling
- Environment-based configuration with DEBUG=1 support

### 3.2 Update `tools.go` - Tool Registration System
- Tool registry with dynamic registration
- Tool metadata (name, description, input schema)
- Tool execution handlers
- Proper error handling and response formatting

## 4. Logging Enhancement

### 4.1 Structured Logging
- Use `log.With().Str("scope", "funcname")` pattern
- DEBUG=1 environment variable support
- Request/response logging in debug mode
- Performance metrics logging

## 5. Testing Infrastructure

### 5.1 Create `test_client.py` - Python Test Client
- Use existing `.venv` environment
- Test all endpoints (initialize, tools/list, tools/call)
- Test database operations (postgres_schemas, mysql_query_select, etc.)
- Validate JSON-RPC compliance
- Test HTTP POST request/response pattern

### 5.2 Update Makefile
- Add `make test-mcp` target
- Add `make lint` for Go linting
- Update build targets

## 6. Cleanup and Documentation

### 6.1 Remove Python Implementation
- Delete `mcp_server/` directory
- Delete `mcp_client/` directory
- Remove Python-related files (pyproject.toml, uv.lock)

### 6.2 Update Documentation
- Update README.md with Go implementation details
- Update CLAUDE.md with new development commands
- Document HTTP streaming protocol details
- Add API documentation

## 7. File Structure After Implementation
```
/mcp-storage/
├── main.go              # Entry point with Fiber setup
├── config.go            # Environment configuration
├── adapter.go           # Database adapter interface
├── postgres.go          # PostgreSQL adapter
├── mysql.go             # MySQL adapter
├── protocol.go          # MCP protocol types
├── jsonrpc.go          # JSON-RPC implementation
├── transport.go         # HTTP streaming transport
├── tools.go             # Tool registration and execution
├── session.go          # Session management
├── logger.go           # Logging utilities
├── test_client.py      # Python test client
├── .env.example        # Environment example
├── go.mod              # Go dependencies
├── go.sum              # Go dependency checksums
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose setup
├── Makefile            # Build and test commands
└── README.md           # Documentation
```

## 8. Implementation Order
1. ✅ Remove mark3labs/mcp-go dependency from go.mod
2. Implement core protocol types (protocol.go, jsonrpc.go)
3. Create session management (session.go)
4. Update transport.go for HTTP streaming
5. Rewrite tools.go without external MCP library
6. Update main.go to use new implementation
7. Add logging utilities (logger.go)
8. Create Python test client
9. Run linters and fix issues
10. Test with Docker Compose
11. Remove Python implementation
12. Update documentation