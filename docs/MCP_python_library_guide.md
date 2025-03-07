# Model Context Protocol (MCP) Library Guide

## Overview

The Model Context Protocol (MCP) is a standardized communication protocol designed for interactions between Large Language Models (LLMs) and external tools/services. It provides a structured way for applications to extend LLM capabilities by connecting to various data sources and services.

## Key Components

### Protocol Structure

MCP uses JSON-RPC 2.0 as its messaging format and supports multiple transport mechanisms:

- **Server-Sent Events (SSE)**: HTTP-based protocol for push notifications
- **Standard I/O (stdio)**: Direct communication through stdin/stdout for local integrations

### Protocol Lifecycle

1. **Initialization Phase**:
   - Client sends an `initialize` request with capabilities and version
   - Server responds with its capabilities and supported version
   - Client sends an `initialized` notification to indicate readiness

2. **Operation Phase**:
   - Tool discovery and invocation
   - Resource handling and other negotiated capabilities

3. **Shutdown Phase**:
   - Graceful termination using transport-specific mechanisms

### Response Format

Tool responses in MCP follow a standardized structure:

```json
{
  "jsonrpc": "2.0",
  "id": "request_id",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "actual_content_here"
      }
    ],
    "isError": false
  }
}
```

Error responses include an `isError: true` flag and often a `message` field:

```json
{
  "jsonrpc": "2.0",
  "id": "request_id",
  "result": {
    "content": [],
    "isError": true,
    "message": "Error description here"
  }
}
```

## Client Implementation

The Python SDK provides a robust client implementation with the following features:

### Client Class

- **Initialization**: Establishes connection with proper protocol handshake
- **Tool Discovery**: Lists available tools from the server
- **Tool Invocation**: Calls tools with required parameters
- **Response Handling**: Parses complex response structures

### Response Parsing

The `parse_tool_response` function handles parsing MCP responses, which can be challenging due to:

1. Different access patterns (dictionary vs. attribute access)
2. Nested content structures
3. Variations in response format between servers

Best practices for response parsing:

```python
def parse_tool_response(response):
    """
    Parse an MCP tool response to extract text content and error information.
    
    Returns:
        tuple: (value, is_error, error_message)
    """
    try:
        # Extract result object (handles both attribute and dict access)
        result = None
        if hasattr(response, 'result'):
            result = response.result
        elif isinstance(response, dict) and 'result' in response:
            result = response['result']
            
        # Extract content and error info (handles both access patterns)
        content = None
        is_error = False
        error_message = None
        
        # Dictionary approach
        if isinstance(result, dict):
            is_error = result.get('isError', False)
            error_message = result.get('message')
            content = result.get('content')
        
        # Attribute approach
        elif hasattr(result, 'isError'):
            is_error = result.isError
            error_message = getattr(result, 'message', None)
            content = getattr(result, 'content', None)
            
        # Return early if error
        if is_error:
            return None, True, error_message or "Unknown error"
            
        # Extract text from content list
        if not content or not isinstance(content, list) or len(content) == 0:
            return None, False, None
            
        # Get text from first content item
        first_item = content[0]
        text_value = None
        
        # Try multiple extraction methods
        if isinstance(first_item, dict) and 'text' in first_item:
            text_value = first_item['text']
        elif hasattr(first_item, 'text'):
            text_value = first_item.text
        elif isinstance(first_item, dict) and 'type' in first_item and first_item.get('type') == 'text':
            text_value = first_item.get('text')
            
        return text_value, False, None
        
    except Exception as e:
        return None, False, None
```

## Common Issues and Solutions

### Response Parsing Failures

The most common issues with MCP client implementations occur during response parsing:

1. **Access Pattern Mismatch**: Server responses may use dictionary-like structure while code expects attribute access or vice versa
   - **Solution**: Support both access patterns as shown in the parsing function

2. **Nested Content Structure**: The actual content might be deeply nested
   - **Solution**: Implement robust traversal of the response structure

3. **Framework-Specific Serialization**: Some frameworks may add layers to the response object
   - **Solution**: Add debug logging to understand the exact structure of the response

4. **Different Response Formats**: Some servers may implement slight variations of the specification
   - **Solution**: Make the parser flexible enough to handle these variations

### Testing

Testing MCP client implementations should include:

1. **Mock Responses**: Test with various response formats
2. **Edge Cases**: Test with empty responses, errors, and unusual content types
3. **Integration Tests**: Test against actual MCP servers

## Using the MCP Client

### Basic Usage

```python
async def simple_example():
    # Create client with desired transport
    async with SseClientTransport("http://localhost:8000/sse") as transport:
        client = Client(transport)
        
        # Initialize client with server
        await client.initialize()
        
        # List available tools
        await client.list_tools()
        
        # Call a tool
        response = await client.call_tool("tool_name", {"param1": "value1"})
        
        # Parse response
        text_value, is_error, error_message = parse_tool_response(response)
        
        if is_error:
            print(f"Error: {error_message}")
        else:
            print(f"Result: {text_value}")
```

### Debugging Tips

1. Enable verbose logging to understand message exchange:
   ```python
   logging.getLogger("mcp_client").setLevel(logging.DEBUG)
   ```

2. Log response structures to understand parsing issues:
   ```python
   logger.debug(f"Raw response: {response}")
   logger.debug(f"Response type: {type(response)}")
   ```

3. Use try-except blocks with detailed error handling:
   ```python
   try:
       # MCP operations
   except Exception as e:
       logger.error(f"Error: {e}")
       import traceback
       logger.error(traceback.format_exc())
   ```

## Resources

- [Model Context Protocol Specification](https://github.com/modelcontextprotocol/specification)
- [Python SDK GitHub Repository](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Tools Specification](https://spec.modelcontextprotocol.io/specification/2024-11-05/server/tools/)
- [MCP Lifecycle Documentation](https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/lifecycle/) 