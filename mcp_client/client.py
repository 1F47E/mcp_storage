"""
MCP Client implementation with Pydantic models for structured parsing and validation.

This module provides a client implementation for the Model Context Protocol (MCP),
"""

import json
import asyncio
import click
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
import mcp.types as types
import logging
import json
from typing import List, Optional, Union, Dict, Any, Tuple
from pydantic import BaseModel, Field
import sys
import traceback
import pprint
import re

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp_client")

# Tool name constants
TOOL_POSTGRES_SCHEMA_DDLS = "postgres_schema_ddls"
TOOL_POSTGRES_QUERY_SELECT = "postgres_query_select"
TOOL_MYSQL_QUERY_SELECT = "mysql_query_select"
TOOL_RANDOM_UINT64 = "random_uint64"

# Mapping of tools to their primary parameter name for string arguments
TOOL_STRING_PARAM_MAPPING = {
    TOOL_POSTGRES_SCHEMA_DDLS: "schema_name",
    TOOL_POSTGRES_QUERY_SELECT: "query",
    TOOL_MYSQL_QUERY_SELECT: "query",
}

# Function to extract and parse data from 'root=JSONRPCResponse' format
def extract_jsonrpc(input_str: str, field_name: str = None) -> Any:
    """Extract and parse data from MCP 'root=' prefixed response strings.
    
    This function handles the string representation of JSONRPCResponse objects
    returned by the MCP server, extracting the specified field or the entire result.
    
    Args:
        input_str: The string starting with 'root=' to parse
        field_name: Optional name of a specific field to extract from result
                   (if None, returns the entire result object)
    
    Returns:
        The extracted data, which could be a dict, list, string, or other value
        depending on what was requested and found in the response.
    """
    # Make sure we have a root= prefixed string
    if not input_str or not isinstance(input_str, str) or not input_str.startswith('root='):
        logger.debug("Input is not a 'root=' prefixed string")
        return None
    
    # Handle different root= formats    
        
    # Extract the 'result' field content
    match = re.search(r'result=(\{.*?\})', input_str, re.DOTALL)
    if not match:
        logger.debug("No result field found in input string")
        return None
        
    # Try a more comprehensive pattern to extract the entire result object
    # This pattern looks for result={...} with potentially nested objects
    full_result_match = re.search(r'result=(\{.*?\})(?:,\s*error=|\)$)', input_str, re.DOTALL)
    if full_result_match:
        result_str = full_result_match.group(1)
    else:
        result_str = match.group(1)
    
    # Replace single quotes with double quotes for valid JSON
    json_compatible_str = result_str.replace("'", '"')
    # Handle None, True, False values for proper JSON
    json_compatible_str = json_compatible_str.replace("None", "null")
    json_compatible_str = json_compatible_str.replace("True", "true").replace("False", "false")
    
    try:
        result_json = json.loads(json_compatible_str)
        
        # If a specific field was requested, extract it
        if field_name and field_name in result_json:
            return result_json.get(field_name)
        
        # Otherwise return the entire result object
        return result_json
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error while parsing 'root=' string: {e}")
        logger.debug(f"Problem string: {json_compatible_str}")
        
        # Try a fallback parsing approach for complex nested structures
        try:
            # Use ast.literal_eval which can handle nested Python data structures
            import ast
            result_dict = ast.literal_eval(result_str)
            
            # If a specific field was requested, extract it
            if field_name and field_name in result_dict:
                return result_dict.get(field_name)
                
            # Otherwise return the entire result object
            return result_dict
        except Exception as ast_error:
            logger.error(f"Fallback parsing error: {ast_error}")
            return None


# Pydantic models for MCP protocol responses
class TextContent(BaseModel):
    """Model for text content in MCP responses.
    
    Attributes:
        type: The content type (usually 'text')
        text: The actual text content
    """
    type: str
    text: str


class ToolCallResult(BaseModel):
    """Model for tool call results in MCP responses.
    
    Attributes:
        content: List of content items (usually TextContent)
        isError: Whether the tool call resulted in an error
        message: Optional error message
    """
    content: List[Union[TextContent, Dict[str, Any]]]
    isError: bool = False
    message: Optional[str] = None
    
    def get_text_value(self) -> Optional[str]:
        """Convenience method to extract the text from the first content item."""
        if not self.content or len(self.content) == 0:
            return None
            
        first_item = self.content[0]
        # Handle both TextContent objects and dictionaries
        if isinstance(first_item, TextContent):
            return first_item.text
        elif isinstance(first_item, dict) and 'text' in first_item:
            return first_item['text']
        return None


class ToolCallParams(BaseModel):
    """Model for tool call parameters.
    
    Attributes:
        name: Name of the tool to call
        arguments: Dictionary of arguments for the tool
    """
    name: str
    arguments: Dict[str, Any]


class JsonRpcRequest(BaseModel):
    """Model for JSON-RPC request objects.
    
    Attributes:
        jsonrpc: JSON-RPC version (always "2.0")
        id: Request ID
        method: Method name
        params: Parameters for the method
    """
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Union[ToolCallParams, Dict[str, Any]]


class JsonRpcResponse(BaseModel):
    """Model for JSON-RPC response objects.
    
    Attributes:
        jsonrpc: JSON-RPC version (always "2.0")
        id: Response ID matching the request
        result: Result of the method call
        error: Error information if the call failed
    """
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Union[ToolCallResult, Dict[str, Any]]] = None
    error: Optional[Dict[str, Any]] = None


class SseClientTransport:
    """Implementation of a transport that uses the sse_client context manager."""
    
    def __init__(self, url: str):
        self.url = url
        self.streams = None
        self._cm = None
        
    async def __aenter__(self):
        # Store the context manager so we can exit it properly
        logger.debug(f"Creating SSE client context manager for URL: {self.url}")
        self._cm = sse_client(self.url)
        # Get the streams by entering the context manager
        logger.debug("Entering SSE client context manager")
        try:
            self.streams = await self._cm.__aenter__()
            logger.debug(f"Obtained streams: {self.streams}")
            return self
        except Exception as e:
            logger.error(f"Error entering SSE context: {e}")
            logger.error(traceback.format_exc())
            raise
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Exit the context manager properly if it exists
        logger.debug("Exiting SSE client context manager")
        if self._cm:
            try:
                await self._cm.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.error(f"Error exiting SSE context: {e}")
        
    def get_streams(self):
        logger.debug(f"Returning streams: {self.streams}")
        return self.streams


class Client:
    """Low-level MCP client with Pydantic model integration.
    
    This client implements the MCP protocol using JSON-RPC over either
    stdio or SSE transport. It uses Pydantic models to parse and validate
    responses, making it easier to extract values from complex response structures.
    
    Attributes:
        transport: The transport implementation to use
        streams: Tuple of (read_stream, write_stream)
        initialized: Whether the client has been initialized with the server
        available_tools: List of available tools from the server
    """
    
    def __init__(self, transport=None):
        self.transport = transport
        self.streams = None
        self._request_id = 0
        self.initialized = False
        self.available_tools = []
    
    async def initialize(self):
        """Initialize with the provided transport."""
        logger.info("Initializing client...")
        if self.transport:
            logger.debug(f"Getting streams from transport: {self.transport}")
            self.streams = self.transport.get_streams()
            logger.debug(f"Obtained streams: {self.streams}")
            
        # Send initialization request with required parameters
        logger.info("Sending initialization request")
        init_response = await self._send_initialize_request()
        
        # Send initialized notification as required by the MCP protocol
        logger.info("Sending initialized notification")
        await self._send_initialized_notification()
        
        # List tools after initialization
        try:
            logger.info("Requesting tools list after initialization")
            await self.list_tools()
        except Exception as e:
            logger.warning(f"Failed to list tools after initialization: {e}")
            logger.warning(traceback.format_exc())
            # Continue even if tools listing fails
        
        return init_response
        
    async def _send_initialize_request(self):
        """Send an initialization request to the server."""
        if not self.streams:
            logger.error("Client not initialized with streams")
            raise RuntimeError("Client not initialized with streams")
            
        read_stream, write_stream = self.streams
        
        # Create a proper initialization request with the correct protocol version
        request_id = self._get_next_request_id()
        request = types.JSONRPCMessage(
            jsonrpc="2.0",
            id=request_id,
            method="initialize",
            params={
                "protocolVersion": "2024-11-05", # Use correct protocol version
                "capabilities": {
                    # Add minimal capabilities
                    "sampling": {}  # Indicate support for sampling
                },
                "clientInfo": {
                    "name": "MCP Python Client",
                    "version": "0.1.0"
                }
            }
        )
        
        logger.info(f"Sending initialization request: {request}")
        
        # Send the request
        try:
            await write_stream.send(request)
            logger.debug("Request sent successfully")
        except Exception as e:
            logger.error(f"Error sending initialization request: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # Wait for the response
        logger.debug("Waiting for initialization response...")
        try:
            response = await read_stream.receive()
            logger.debug(f"Received raw response type: {type(response)}")
            if hasattr(response, '__dict__'):
                logger.debug(f"Response __dict__: {response.__dict__}")
            else:
                logger.debug(f"Raw response: {response}")
        except Exception as e:
            logger.error(f"Error receiving initialization response: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # Check if we received an exception
        if isinstance(response, Exception):
            logger.error(f"Received exception during initialization: {response}")
            raise response
            
        logger.info(f"Received initialization response: {response}")
        
        # More detailed inspection of the response structure
        logger.debug("Detailed inspection of initialization response:")
        try:
            if hasattr(response, '__dict__'):
                logger.debug(f"Response attributes: {dir(response)}")
                for attr in dir(response):
                    if not attr.startswith('_') and not callable(getattr(response, attr)):
                        logger.debug(f"  {attr}: {getattr(response, attr)}")
        except Exception as e:
            logger.error(f"Error inspecting response: {e}")
        
        print(f"raw init response : {response}")

        
        self.initialized = True
            
        return response
    
    async def _send_initialized_notification(self):
        """Send the initialized notification to the server."""
        if not self.streams:
            raise RuntimeError("Client not initialized with streams")
            
        _, write_stream = self.streams
        
        # Create the initialized notification according to the MCP protocol
        notification = types.JSONRPCMessage(
            jsonrpc="2.0",
            method="notifications/initialized",
            # Notifications don't have an id or params
        )
        
        logger.info("Sending initialized notification")
        
        # Send the notification
        try:
            await write_stream.send(notification)
            logger.debug("Initialized notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending initialized notification: {e}")
            logger.error(traceback.format_exc())
        
    def _get_next_request_id(self):
        """Get the next request ID."""
        self._request_id += 1
        return str(self._request_id)
        
    async def initialize_with_streams(self, read_stream, write_stream):
        """Initialize with the provided streams."""
        self.streams = (read_stream, write_stream)
        
        # Send initialization request and notification
        await self._send_initialize_request()
        await self._send_initialized_notification()
    
    async def list_tools(self):
        """List available tools from the server."""
        if not self.streams or not self.initialized:
            logger.error("Client not initialized. Cannot list tools.")
            raise RuntimeError("Client not initialized")
            
        read_stream, write_stream = self.streams
        
        # Create a request to list tools
        request_id = self._get_next_request_id()
        request = types.JSONRPCMessage(
            jsonrpc="2.0",
            id=request_id,
            method="tools/list",
            params={}
        )
        
        logger.info(f"Requesting tools list with request ID: {request_id}")
        
        try:
            # Send the request
            logger.debug(f"Sending tools/list request: {request}")
            await write_stream.send(request)
            logger.debug("tools/list request sent successfully")
            
            # Wait for the response with timeout
            try:
                logger.debug("Waiting for tools/list response...")
                response = await asyncio.wait_for(read_stream.receive(), timeout=5.0)
                logger.debug(f"Received raw tools/list response type: {type(response)}")
                extract = extract_jsonrpc(response)
                print(f"extract: {extract}")
                if hasattr(response, '__dict__'):
                    logger.debug(f"Response __dict__: {response.__dict__}")
                else:
                    logger.debug(f"Raw response: {response}")
                    # If it's a string, try to parse as JSON
                    if isinstance(response, str):
                        try:
                            if response.startswith("root="):
                                logger.debug("Response starts with 'root=', stripping prefix")
                                clean_response = response[5:]  # Remove 'root=' prefix
                            else:
                                clean_response = response
                            json_data = json.loads(clean_response)
                            logger.debug(f"Parsed JSON: {json_data}")
                        except Exception as e:
                            logger.error(f"Error parsing response as JSON: {e}")
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for tools/list response")
                return None
            except Exception as e:
                logger.error(f"Exception while waiting for tools/list response: {e}")
                logger.error(traceback.format_exc())
                return None
            
            # Check if we received an exception
            if isinstance(response, Exception):
                logger.error(f"Failed to list tools: {response}")
                return None
            
            logger.info(f"Received tools list response: {response}")
            
            # More detailed inspection of the response structure
            logger.debug("Detailed inspection of tools/list response:")
            try:
                if hasattr(response, '__dict__'):
                    logger.debug(f"Response attributes: {dir(response)}")
                    for attr in dir(response):
                        if not attr.startswith('_') and not callable(getattr(response, attr)):
                            logger.debug(f"  {attr}: {getattr(response, attr)}")
            except Exception as e:
                logger.error(f"Error inspecting response: {e}")


            # Parse the tools list from the response
            try:
                print(f"response: {response}")
                response_str = str(response)
                print(f"\n\nResponse as string: {response_str}\n\n")

                # Initialize tools list
                self.available_tools = []
                # Handle root= prefix and extract tools list
                if response_str.startswith("root="):
                    # Use the extract_jsonrpc function to get tools
                    tools = extract_jsonrpc(response_str, "tools")
                    if tools:
                        self.available_tools = tools
                        print(f"available_tools: {self.available_tools}")
                
                # Fallback to parsing response.result directly
                # elif hasattr(response, 'result') and isinstance(response.result, dict):
                    # self.available_tools = response.result.get('tools', [])

                # Print available tools
                if self.available_tools:
                    print("\nAvailable tools:")
                    print("==================================================")
                    for tool in self.available_tools:
                        name = tool.get('name', 'Unknown')
                        description = tool.get('description', 'No description available')
                        print(f"-- tool {name}")
                        print(f"  {description}")
                        print("==================================================")
                else:
                    logger.warning("No tools found in the response")
                    print("\nNo tools available")

            except Exception as e:
                logger.error(f"Error parsing tools list: {e}")
                logger.error(traceback.format_exc())
            
            return response
        except Exception as e:
            logger.error(f"Unexpected error in list_tools: {e}")
            logger.error(traceback.format_exc())
            return None


    async def call_tool(self, tool_name: str, params: dict):
        """Call a tool with the given parameters."""
        if not self.streams:
            raise RuntimeError("Client not initialized with streams")
            
        # Make sure we're initialized with the server
        if not self.initialized:
            logger.info("Client not initialized with server, initializing now...")
            await self._send_initialize_request()
            await self._send_initialized_notification()
                
        read_stream, write_stream = self.streams
        
        # Create a request message using Pydantic
        request_id = self._get_next_request_id()
        tool_params = ToolCallParams(name=tool_name, arguments=params)
        request_model = JsonRpcRequest(
            id=request_id,
            method="tools/call",
            params=tool_params
        )
        
        # Convert to the format expected by the stream
        request = types.JSONRPCMessage(
            jsonrpc=request_model.jsonrpc,
            id=request_model.id,
            method=request_model.method,
            params={
                "name": tool_params.name,
                "arguments": tool_params.arguments
            }
        )
        
        logger.info(f"Sending tool call request: {request}")
        
        # Send the request
        await write_stream.send(request)
        
        # Wait for the response
        response = await read_stream.receive()
        
        # Check if we received an exception
        if isinstance(response, Exception):
            logger.error(f"Received exception during tool call: {response}")
            raise response
            
        logger.info(f"Received tool call response: {response}")

        # First, check if response is a string with "root=" prefix and use our extraction function
        if isinstance(response, str) and response.startswith("root="):
            logger.debug("Response is a root= prefixed string, using extract_jsonrpc")
            result = extract_jsonrpc(response)
            
            if result and 'content' in result and isinstance(result['content'], list) and len(result['content']) > 0:
                # Get the first content item
                content_item = result['content'][0]
                if isinstance(content_item, dict) and 'text' in content_item:
                    logger.info(f"Found text content in response: {content_item['text'][:50]}...")
                    return content_item['text']
                    
            # If we couldn't extract content, try simple text regex as fallback
            text_match = re.search(r"'text':\s*'([^']+)'", response)
            if text_match:
                text_value = text_match.group(1)
                logger.info(f"Extracted text via regex: {text_value[:50]}...")
                return text_value

        # Handle regular response object case if the above extraction didn't work
        try:
            import pprint
            
            # Convert response to string first
            response_str = str(response)
            logger.debug(f"Response string: {response_str}")
            
            # Check if it's the root=JSONRPCResponse format that wasn't handled above
            if response_str.startswith("root=JSONRPCResponse") and not isinstance(response, str):
                logger.debug("Converting non-string response to string and using extract_jsonrpc")
                result = extract_jsonrpc(response_str)
                
                if result and 'content' in result:
                    content_list = result['content']
                    for content_item in content_list:
                        if isinstance(content_item, dict) and content_item.get('type') == 'text' and 'text' in content_item:
                            print(f"\n\n{content_item['text']}")
                            return content_item['text']
            
            # Handle regular object response with result.content attribute
            if hasattr(response, 'result') and hasattr(response.result, 'content'):
                logger.debug("Processing response with result.content attribute")
                content_list = response.result.content
                
                # Process each content item
                for content_item in content_list:
                    if hasattr(content_item, 'type') and content_item.type == 'text':
                        if hasattr(content_item, 'text'):
                            logger.info("Found text content in response")
                            return content_item.text
                
                # If we didn't find text content but have content
                logger.warning("No text content found in response content")
                pp = pprint.PrettyPrinter(indent=2)
                logger.debug(f"Content structure: {pp.pformat(content_list)}")
                return content_list
            # Try to parse as JSON if it's a string
            if isinstance(response, str):
                try:
                    json_data = json.loads(response)
                    if 'result' in json_data and 'content' in json_data['result']:
                        for content_item in json_data['result']['content']:
                            if content_item.get('type') == 'text' and 'text' in content_item:
                                return content_item['text']
                except json.JSONDecodeError:
                    pass
            
            logger.warning("Could not extract content from response structure")
            return response
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return response
        # Return the response that will be parsed by Pydantic in the caller
        return response


async def call_random_tool(client):
    """Call the random_uint64 tool and print the result."""
    print(f"Calling {TOOL_RANDOM_UINT64} tool...")
    try:
        raw_response = await client.call_tool(TOOL_RANDOM_UINT64, {})
        
        # Log the raw response for debugging
        logger.debug(f"Raw response from {TOOL_RANDOM_UINT64}: {raw_response}")
        
        # Handle root= prefix using our extraction function
        if isinstance(raw_response, str) and raw_response.startswith("root="):
            logger.debug("Using extract_jsonrpc for root= prefixed response")
            
            # Extract the result
            result = extract_jsonrpc(raw_response)
            if result and 'content' in result and len(result['content']) > 0:
                # Look for text in the first content item
                content_item = result['content'][0]
                if isinstance(content_item, dict) and 'text' in content_item:
                    print(f"Random number: {content_item['text']}")
                    return
            
            # If that didn't work, try regex as fallback
            match = re.search(r"'text': '(\d+)'", raw_response)
            if match:
                number = match.group(1)
                print(f"Random number: {number}")
                return
        
        # If direct handling didn't work, fall back to general parser
        value, is_error, error_message = parse_tool_response(raw_response)
        
        if is_error:
            print(f"Error: {error_message or 'Unknown error'}")
        elif value:
            print(f"Random number: {value}")
        else:
            print(f"Raw response: {raw_response}")
            
    except Exception as e:
        print(f"Error calling random_uint64 tool: {e}")
        import traceback
        traceback.print_exc()


# Utility function to parse tool responses
def parse_tool_response(response):
    """Parse an MCP tool response using Pydantic models.
    
    This function handles the various response formats that might be returned by an MCP server,
    normalizing them to Pydantic models for structured access and validation.
    
    Args:
        response: The raw response from the MCP server
        
    Returns:
        tuple: (value, is_error, error_message)
            - value: The extracted value from the response (text content or None)
            - is_error: Boolean indicating if this was an error response
            - error_message: Error message string if is_error is True, otherwise None
    """
    try:
        # Enhanced logging for understanding the response structure
        logger.debug(f"Parsing response type: {type(response)}")
        logger.debug(f"Response representation: {repr(response)}")
        
        # Handle case where response is a string with "root=" prefix
        if isinstance(response, str) and response.startswith("root="):
            logger.debug("Using extract_jsonrpc to parse root= prefixed response")
            
            # Get the result object using our extraction function
            result = extract_jsonrpc(response)
            if result:
                # Check for error in the result
                is_error = result.get('isError', False)
                if is_error:
                    error_message = result.get('message', 'Unknown error')
                    return None, True, error_message
                
                # Check for content items
                if 'content' in result and isinstance(result['content'], list) and len(result['content']) > 0:
                    content_item = result['content'][0]
                    if isinstance(content_item, dict) and 'text' in content_item:
                        return content_item['text'], False, None
            
            # If the extraction didn't give us usable results, try direct regex
            # Look for text content in the response
            text_match = re.search(r"'text':\s*'([^']+)'", response)
            if text_match:
                text_value = text_match.group(1)
                logger.debug(f"Extracted text via regex: {text_value}")
                return text_value, False, None
        
        # Check if it's a complex Object with result attribute
        if hasattr(response, 'result'):
            logger.debug("Found result attribute on response object")
            result = response.result
            
            # Handle different result formats
            if hasattr(result, 'content') and getattr(result, 'content'):
                # It has a content list we can try to extract from
                content = getattr(result, 'content')
                if content and len(content) > 0:
                    first_item = content[0]
                    if hasattr(first_item, 'text'):
                        return getattr(first_item, 'text'), False, None
                    elif isinstance(first_item, dict) and 'text' in first_item:
                        return first_item['text'], False, None
            elif isinstance(result, dict) and 'content' in result:
                # Result is a dictionary with content
                content = result['content']
                if content and len(content) > 0:
                    first_item = content[0]
                    if isinstance(first_item, dict) and 'text' in first_item:
                        return first_item['text'], False, None
        
        # If we couldn't extract in a structured way, try simple regex as a last resort
        if isinstance(response, str):
            # Look for text content in the response
            text_match = re.search(r"'text':\s*'([^']+)'", response)
            if text_match:
                return text_match.group(1), False, None
                
        # If we get here, we couldn't extract the text value
        logger.warning("Could not extract text value from response")
        return None, False, None
        
    except Exception as parse_error:
        logger.error(f"Error parsing tool response: {parse_error}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Last resort parsing - try to directly extract text using regex
        if isinstance(response, str):
            # Look for text content in the response
            text_match = re.search(r"'text':\s*'([^']+)'", response)
            if text_match:
                return text_match.group(1), False, None
                
        return None, False, None


async def call_any_tool(client, tool_name, arguments=None):
    """Call any tool and display the result.
    
    Args:
        client: The MCP client instance
        tool_name: Name of the tool to call
        arguments: Optional dict of arguments for the tool (default: {})
        
    Returns:
        The extracted value from the tool response
    """
    if arguments is None:
        arguments = {}
    
    # Special handling for tools that require specific parameters
    if tool_name in TOOL_STRING_PARAM_MAPPING:
        param_name = TOOL_STRING_PARAM_MAPPING[tool_name]
        # Check if the required parameter is provided
        if not arguments.get(param_name):
            print(f"Error: {tool_name} requires a {param_name} parameter")
            if tool_name == TOOL_POSTGRES_SCHEMA_DDLS:
                print("Example: --args public")
            elif tool_name == TOOL_POSTGRES_QUERY_SELECT:
                print("Example: --args \"SELECT * FROM table LIMIT 1\"")
            return None
        
        # For postgres_schema_ddls, display schema name
        if tool_name == TOOL_POSTGRES_SCHEMA_DDLS:
            schema_name = arguments.get(param_name)
            print(f"Calling {tool_name} tool for schema: {schema_name}...")
        else:
            print(f"Calling {tool_name} tool...")
    else:
        print(f"Calling {tool_name} tool...")
    
    # Print nicely formatted arguments for better visibility
    if arguments:
        print("Arguments:")
        for key, value in arguments.items():
            print(f"  {key}: {value}")
    
    try:
        # Call the tool
        raw_response = await client.call_tool(tool_name, arguments)
        
        # Parse the response
        value, is_error, error_message = parse_tool_response(raw_response)
        
        # Display the result
        if is_error:
            print(f"Error: {error_message or 'Unknown error'}")
        else:
            print(f"Result: {value}")
            
        return value
    except Exception as e:
        print(f"Error calling {tool_name} tool: {e}")
        import traceback
        traceback.print_exc()
        return None




@click.command()
@click.option("--port", default=8000, help="Port to connect to for SSE")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--verbose", is_flag=True, help="Show detailed logs")
@click.option("--tool", default=None, help="Tool name to call directly")
@click.option("--args", default="{}", help="Tool arguments (simple value or JSON string)")
def main(port: int, transport: str, debug: bool, verbose: bool, tool: str, args: str) -> int:
    """MCP client for interacting with an MCP server.
    
    If no tool is specified, lists the available tools.
    If a tool is specified, calls that tool with the provided arguments.
    
    Examples:
      # List all available tools
      uv run client --transport sse --port 8000
      
      # Call postgres_schema_ddls with schema 'public'
      uv run client --transport sse --port 8000 --tool postgres_schema_ddls --args public
      
      # Call postgres_schema_ddls with schema 'accounting'
      uv run client --transport sse --port 8000 --tool postgres_schema_ddls --args accounting
      
      # Call postgres_query_select with a SQL query
      uv run client --transport sse --port 8000 --tool postgres_query_select --args "SELECT * FROM users LIMIT 10"
      
      # For tools with multiple arguments, use JSON format:
      uv run client --transport sse --port 8000 --tool some_tool --args '{"param1": "value1", "param2": "value2"}'
    """
    
    # Parse arguments with special handling for tools with string parameters
    try:
        # First try to parse as JSON
        tool_args = json.loads(args)
    except json.JSONDecodeError:
        # If parsing as JSON fails, check if the tool supports simple string arguments
        if tool in TOOL_STRING_PARAM_MAPPING:
            # Get the parameter name for this tool
            param_name = TOOL_STRING_PARAM_MAPPING[tool]
            print(f"Converting simple argument to {param_name} parameter")
            tool_args = {param_name: args}
        else:
            # Tool doesn't support simple string arguments
            # Show suggestions for supported tools
            if tool in TOOL_STRING_PARAM_MAPPING:
                param_name = TOOL_STRING_PARAM_MAPPING[tool]
                print(f"Error: Invalid argument format for {tool}.")
                if tool == TOOL_POSTGRES_SCHEMA_DDLS:
                    print(f"Use simple format: --args public")
                elif tool == TOOL_POSTGRES_QUERY_SELECT:
                    print(f"Use simple format: --args \"SELECT * FROM table LIMIT 1\"")
                    print(f"Note: Make sure to quote your SQL query with double quotes!")
                print(f"Or JSON format: --args '{{'{param_name}': 'value'}}'")
            else:
                print(f"Error: Invalid JSON in arguments: {args}")
                print(f"Use format: --args '{{'param_name': 'param_value'}}'")
                print(f"For SQL queries or arguments with spaces, make sure to quote them: --args \"your query\"")
                
                # Display supported tools with simple string arguments
                if TOOL_STRING_PARAM_MAPPING:
                    print("\nThese tools support simple string arguments:")
                    for supported_tool, param in TOOL_STRING_PARAM_MAPPING.items():
                        print(f"  - {supported_tool} (parameter: {param})")
            return 1
    
    # Configure logging based on flags
    if debug:
        # Debug includes everything
        logging.getLogger("mcp_client").setLevel(logging.DEBUG)
        logging.getLogger("mcp").setLevel(logging.DEBUG)  # Also enable MCP SDK debug logging
        print("Debug logging enabled")
    elif verbose:
        # Verbose shows info level logs
        logging.getLogger("mcp_client").setLevel(logging.INFO)
        logging.getLogger("mcp").setLevel(logging.INFO)
        print("Verbose logging enabled")
    else:
        # If neither verbose nor debug, set to WARNING to hide info logs
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("mcp_client").setLevel(logging.WARNING)
        logging.getLogger("mcp").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        
    if transport == "sse":
        async def sse_run():
            # Connect to the SSE server on specified port
            server_url = f"http://localhost:{port}/sse"
            print(f"Connecting to MCP server on {server_url}...")
            logger.info(f"Connecting to MCP server on {server_url}")
            
            try:
                # Use SseClientTransport as an async context manager
                logger.debug("Creating SseClientTransport")
                async with SseClientTransport(server_url) as transport:
                    # Create client and initialize it
                    logger.debug("Creating Client")
                    client = Client(transport)
                    
                    # Initialize client and get tools list
                    print("Initializing client...")
                    logger.info("Initializing client")
                    await client.initialize()
                    
                    # If a tool was specified, call it
                    if tool:
                        logger.info(f"Tool specified: {tool}")
                        if tool == TOOL_RANDOM_UINT64:
                            await call_random_tool(client)
                        else:
                            # Validate required parameters for tools that need them
                            if tool in TOOL_STRING_PARAM_MAPPING:
                                param_name = TOOL_STRING_PARAM_MAPPING[tool]
                                if not tool_args.get(param_name):
                                    print(f"Error: {tool} requires a {param_name} parameter.")
                                    if tool == TOOL_POSTGRES_SCHEMA_DDLS:
                                        print("Example: --args public")
                                    elif tool == TOOL_POSTGRES_QUERY_SELECT:
                                        print("Example: --args \"SELECT * FROM table LIMIT 1\"")
                                    return 1
                            
                            await call_any_tool(client, tool, tool_args)
                    else:
                        # Otherwise, just list the available tools
                        logger.info("No tool specified, listing available tools")
                        
            except Exception as e:
                print(f"Error: {e}")
                logger.error(f"Error in sse_run: {e}")
                logger.error(traceback.format_exc())
                return 1
            
            return 0
            
        return asyncio.run(sse_run())
    else:
        # Use stdio transport
        async def stdio_run():
            print("Using stdio transport to connect to MCP server...")
            
            try:
                # Run the llm directly with the command and in the same process
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "mcp.cli.run", 
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                )
                
                # Create stream wrappers
                read_stream = types.AsyncIteratorReadStream(proc.stdout)
                write_stream = types.AsyncWriteStream(proc.stdin)
                
                # Create client with proper initialization
                client = Client()
                client.streams = (read_stream, write_stream)
                
                # Initialize the client with the server
                print("Initializing client...")
                await client.initialize()
                
                # If a tool was specified, call it
                if tool:
                    if tool == TOOL_RANDOM_UINT64:
                        await call_random_tool(client)
                    else:
                        await call_any_tool(client, tool, tool_args)
                    
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                return 1
            
            return 0
            
        return asyncio.run(stdio_run())


if __name__ == "__main__":
    main() 