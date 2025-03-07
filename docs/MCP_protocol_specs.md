# Model Context Protocol (MCP) Implementation

This repository contains a Python implementation of the Model Context Protocol (MCP), a standardized communication protocol designed for interactions between language models and external tools/services.

## Overview

The Model Context Protocol enables language models to interact with external systems through a standardized interface. This implementation includes both client and server components that communicate using JSON-RPC over various transport mechanisms.

## Protocol Specification

### Version

This implementation complies with the MCP specification version `2024-11-05`.

### Protocol Lifecycle

The MCP defines a rigorous lifecycle for client-server connections:

1. **Initialization Phase**:
   - Client sends an `initialize` request with its capabilities and version
   - Server responds with its capabilities and supported version
   - Client sends an `initialized` notification to indicate readiness

2. **Operation Phase**:
   - Normal protocol operations including tool discovery and invocation
   - Resource handling and other capabilities as negotiated

3. **Shutdown Phase**:
   - Graceful termination of the connection using transport-specific mechanisms

### Transport Mechanisms

This implementation supports two transport mechanisms:

- **Server-Sent Events (SSE)**: HTTP-based protocol for push notifications from server to client
- **Standard I/O (stdio)**: Direct communication through stdin/stdout for local integrations

### Core Features

#### Initialization

```json
// Client -> Server
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "sampling": {}
    },
    "clientInfo": {
      "name": "MCP Python Client",
      "version": "0.1.0"
    }
  }
}

// Server -> Client
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {
        "listChanged": true
      }
    },
    "serverInfo": {
      "name": "MCP Test Server",
      "version": "0.1.0"
    }
  }
}

// Client -> Server
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

#### Tool Discovery

```json
// Client -> Server
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "tools/list",
  "params": {}
}

// Server -> Client
{
  "jsonrpc": "2.0",
  "id": "2",
  "result": {
    "tools": [
      {
        "name": "random_uint64",
        "description": "Generates a random unsigned 64-bit integer (uint64)",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      }
    ]
  }
}
```

#### Tool Invocation

```json
// Client -> Server
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "tools/call",
  "params": {
    "name": "random_uint64",
    "arguments": {}
  }
}

// Server -> Client
{
  "jsonrpc": "2.0",
  "id": "3",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "12345678901234567890"
      }
    ],
    "isError": false
  }
}
```

## Client Implementation

The client implementation is divided into several components:

### SseClientTransport

Manages SSE connections to the server:
- Establishes connection to the server endpoint
- Provides read/write streams for communication
- Handles proper connection lifecycle

### Client Class

Main client implementation with methods for:
- Initializing the connection
- Discovering available tools
- Invoking tools with parameters
- Parsing tool responses

Key features:
- Proper error handling with timeout support
- Robust parsing of different response formats
- Debug logging for troubleshooting

## Server Implementation

The server implementation includes:

### Tools Registration

```python
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="random_uint64",
            description="Generates a random unsigned 64-bit integer (uint64)",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        )
    ]
```

### Tool Implementation

```python
@app.call_tool()
async def fetch_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "random_uint64":
        random_uint64 = random.randint(0, 2**64 - 1)
        return [types.TextContent(type="text", text=str(random_uint64))]
    else:
        raise ValueError(f"Unknown tool: {name}")
```

### Server Configuration

The server supports both SSE and stdio transports, and can be configured with command-line options.

## Usage

### Running the Server

```bash
# Run with SSE transport on port 8000
uv run mcp-simple-tool --transport sse --port 8000

# Run with stdio transport
uv run mcp-simple-tool --transport stdio
```

### Running the Client

```bash
# Connect to server with SSE transport
uv run client --transport sse --port 8000 --debug

# Connect to server with stdio transport
uv run client --transport stdio --debug
```

## Error Handling

The implementation includes robust error handling for:
- Connection issues
- Protocol version mismatches
- Timeout handling for requests
- Invalid responses
- Tool invocation errors

## Debugging

Debug logging is available through the `--debug` flag, which provides detailed information about:
- Message exchange
- Protocol state transitions
- Parsing errors
- Tool invocation details

## Implementation Notes

### Common Issues

1. **Protocol Version**: Ensure the `protocolVersion` is set to `2024-11-05` not older versions
2. **Initialization Flow**: Always send the `initialized` notification after receiving the initialization response
3. **Response Parsing**: Handle both standard and non-standard response formats gracefully
4. **Timeouts**: Implement timeouts for all requests to avoid hanging
5. **Error Handling**: Always wrap tool calls in try/except blocks

### Security Considerations

1. Validate all tool inputs
2. Implement proper access controls
3. Rate limit tool invocations
4. Sanitize tool outputs
5. Consider user confirmation for sensitive operations

## References

- [Model Context Protocol Specification](https://github.com/modelcontextprotocol/specification)
- [MCP Tools Specification](https://spec.modelcontextprotocol.io/specification/2024-11-05/server/tools/)
- [MCP Lifecycle Documentation](https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/lifecycle/) 