# Server command to run the MCP server with SSE transport
.PHONY: server
server:
	uv run mcp_server --transport sse --port 8000

# Client command to run the client with SSE transport
.PHONY: client
client:
	uv run client --transport sse --port 8000 --verbose

