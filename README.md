# MCP Storage Server

A Go implementation of the Model Context Protocol (MCP) server that provides database connectivity tools for LLMs. This server enables AI assistants like Claude to interact with PostgreSQL and MySQL databases through a standardized protocol.

## Features

- **Pure HTTP Transport**: No SSE, just simple request-response over HTTP POST
- **Database Support**: PostgreSQL and MySQL adapters with full query capabilities
- **MCP Protocol**: Implements MCP specification version 2024-11-05
- **Extensible Architecture**: Easy to add new database adapters
- **Session Management**: Optional session support with configurable TTL
- **OAuth Mock**: Built-in OAuth endpoints for Claude Code compatibility
- **Docker Support**: Run in containers with proper host database access

## Quick Start

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mcp-storage.git
cd mcp-storage
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env to add your database connection strings
```

3. Build and run:
```bash
make build
make run
```

### Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f mcp-storage

# Stop
docker-compose down
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Server Configuration
PORT=5435
HOST=0.0.0.0
LOG_LEVEL=info

# PostgreSQL Adapter (optional)
POSTGRES_URL=postgresql://user:password@localhost:5432/dbname?sslmode=disable

# MySQL Adapter (optional)
MYSQL_URL=user:password@tcp(localhost:3306)/dbname?charset=utf8mb4&parseTime=True
```

### Logging

Control log verbosity with the LOG_LEVEL environment variable:
```bash
# Available levels: trace, debug, info, warn, error
LOG_LEVEL=debug ./mcp-storage
```

## Available Tools

### PostgreSQL Tools (when configured)
- `postgres_schemas` - List all schemas in the database
- `postgres_schema_ddls` - Get DDL statements for a schema
- `postgres_query_select` - Execute SELECT queries

### MySQL Tools (when configured)
- `mysql_query_select` - Execute SELECT queries
- `mysql_schema_ddls` - Get DDL statements for a schema

## Testing

### Run Tests
```bash
# Test with Python client
make test-mcp

# Test with debug output
make test-mcp-debug

# Test specific tool
python3 test_client.py --tool postgres_schemas
```

### Manual Testing
```bash
# Health check
curl http://localhost:5435/health

# Initialize
curl -X POST http://localhost:5435/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "Test Client",
        "version": "1.0.0"
      }
    }
  }'
```

## Development

### Project Structure
```
/mcp-storage/
├── main.go              # Entry point
├── config.go            # Environment configuration
├── adapter.go           # Database adapter interface
├── postgres.go          # PostgreSQL implementation
├── mysql.go             # MySQL implementation
├── protocol.go          # MCP protocol types
├── jsonrpc.go          # JSON-RPC handler
├── transport.go         # HTTP transport layer
├── tools.go             # Tool implementations
├── session.go          # Session management
├── logger.go           # Logging utilities
├── test_client.py      # Python test client
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose setup
└── Makefile            # Build commands
```

### Adding New Database Adapters

1. Create a new adapter file (e.g., `redis.go`)
2. Implement the `DatabaseAdapter` interface
3. Register in `main.go`
4. Add tools in `tools.go`

### Commands

```bash
make build          # Build the server
make run           # Run locally
make run-debug     # Run with debug logging
make lint          # Run linters
make clean         # Clean build artifacts
make docker-build  # Build Docker image
make docker-up     # Start with Docker
make docker-logs   # View Docker logs
```

## Integration with Claude

This server is designed to work with Claude Desktop via the MCP protocol. Configure it in Claude's settings to enable database access through the chat interface.

### Claude Desktop Configuration

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "mcp-storage": {
      "command": "docker",
      "args": ["run", "-p", "5435:5435", "--env-file", ".env", "mcp-storage"],
      "type": "http",
      "url": "http://localhost:5435"
    }
  }
}
```

## Using with Cursor

The server also works with Cursor AI. Add the following to your Cursor settings:

1. Open Cursor Settings (Cmd/Ctrl + ,)
2. Search for "MCP" in the settings
3. Add a new MCP server with these settings:
   - **Name**: mcp-storage
   - **Command**: http://localhost:5435
   - **Transport**: HTTP

Or add directly to your Cursor configuration file:

```json
{
  "mcpServers": {
    "mcp-storage": {
      "transport": "http",
      "url": "http://localhost:5435"
    }
  }
}
```

4. Run the server: `docker-compose up -d`
5. Restart Cursor to connect to the MCP server
6. The database tools will be available in your AI chat

## Security Considerations

- Always use read-only database credentials when possible
- The server only allows SELECT queries for safety
- Use SSL/TLS connections for production databases
- Never expose the server directly to the internet
- Validate and sanitize all inputs

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.