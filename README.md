# Model Context Protocol (MCP) with Python Implementation

## What is MCP?

The Model Context Protocol (MCP) is a standardized communication protocol designed for interactions between Large Language Models (LLMs) and external tools/services. It provides a structured way for applications to extend LLM capabilities by connecting to various data sources and services.

MCP uses JSON-RPC 2.0 as its messaging format and supports multiple transport mechanisms:
- **Server-Sent Events (SSE)**: HTTP-based protocol for push notifications
- **Standard I/O (stdio)**: Direct communication through stdin/stdout for local integrations

## Available MCP Server Tools

This implementation includes several built-in tools that can be accessed through the MCP protocol:

- **random_uint64**: Generates a random 64-bit unsigned integer (just for testing)
- **postgres_schemas**: Retrieves PostgreSQL database schema information
- **postgres_schema_ddls**: Gets DDL statements for a specific PostgreSQL schema
- **postgres_query_select**: Executes a SELECT query on a PostgreSQL database
- **mysql_query_select**: Executes a SELECT query on a MySQL database
- **mysql_schema_ddls**: Gets DDL statements for a specific MySQL schema

## MCP Python Client with Pydantic

A Python client for the Model Context Protocol (MCP) with robust response parsing using Pydantic models.

## Features

- **Structured Response Parsing**: Uses Pydantic models to parse and validate JSON-RPC responses
- **Multiple Transport Support**: 
  - Server-Sent Events (SSE) for HTTP-based implementations
  - Standard I/O (stdio) for direct integration
- **Robust Error Handling**: Gracefully handles different response formats and error cases
- **Command-Line Interface**: Easy testing of MCP tools from the command line
- **Configurable Logging**: Control logging verbosity with `--verbose` and `--debug` flags

## Installation

```bash
# Install from the current directory
pip install -e .

# Or install dependencies directly
pip install pydantic click httpx
```

## Quick Start

### Starting the MCP Server

Start the MCP server using the SSE transport:

```bash
# Using uv
uv run mcp_server --transport sse --port 8000
```

### Using the MCP Client

List available tools:

```bash
# Using uv with SSE transport
uv run client --transport sse --port 8000
```

Call a specific tool with arguments:

```bash
# Call random_uint64 tool (for testing)
uv run client --transport sse --port 8000 --tool random_uint64

# Call postgres_schemas tool
uv run client --transport sse --port 8000 --tool postgres_schemas 

# Call a tool with arguments
uv run client --transport sse --port 8000 --tool postgres_schema_ddls --args '{"schema_name": "public"}'
```

Using stdio transport (for piping to a server):

```bash
uv run client --transport stdio
```

## Pydantic Integration

This client uses Pydantic models to parse and validate MCP responses, making it easier to extract values from complex nested structures. The key models include:

- `TextContent`: For text content items in responses
- `ToolCallResult`: For tool call results with content, isError, and message fields
- `JsonRpcRequest`: For outgoing requests
- `JsonRpcResponse`: For incoming responses

The `parse_tool_response` function handles various response formats that might be returned by different MCP server implementations, providing a consistent interface for extracting values.

## Command-Line Options

```
--port INTEGER               Port to connect to for SSE [default: 8000]
--transport [stdio|sse]      Transport type [default: stdio]
--debug                      Enable debug logging
--verbose                    Show detailed logs
--tool TEXT                  Tool name to call [default: random_uint64]
--args TEXT                  JSON string of tool arguments [default: {}]
--help                       Show this message and exit
```

## Logging Control

Three levels of logging are available:

- **Default (no flags)**: Only show essential output, no logs
- **`--verbose`**: Show informational logs (INFO level)
- **`--debug`**: Show all debugging logs (DEBUG level)

## Example Usage

### Basic Usage

```python
from mcp_client.client import Client, SseClientTransport, parse_tool_response

async def example():
    # Connect to MCP server using SSE transport
    async with SseClientTransport("http://localhost:8000/sse") as transport:
        # Create and initialize client
        client = Client(transport)
        await client.initialize()
        
        # Call a tool and parse the response
        response = await client.call_tool("random_uint64", {})
        value, is_error, error_message = parse_tool_response(response)
        
        if not is_error:
            print(f"Tool returned: {value}")
        else:
            print(f"Error: {error_message}")
```

### Adding a New Tool Call

```python
async def call_custom_tool(client, text):
    # Call a hypothetical text generation tool
    response = await client.call_tool("generate_text", {"prompt": text})
    
    # Parse and return the value
    value, is_error, error_message = parse_tool_response(response)
    if is_error:
        print(f"Error: {error_message}")
        return None
    return value
```

## MCP Protocol Compliance

This client implements the MCP specification version `2024-11-05` and follows the protocol lifecycle:

1. **Initialization Phase**: Client sends capabilities and version, server responds, client confirms
2. **Operation Phase**: Tool discovery and invocation
3. **Shutdown Phase**: Graceful termination

## Development

To set up for development:

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

## License

[MIT License](LICENSE)
