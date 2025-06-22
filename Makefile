# Server command to run the MCP server with HTTP transport
.PHONY: server
server:
	uv run mcp-storage --transport http --port 5435

# Client command to run the client with HTTP transport
.PHONY: client
client:
	uv run client --transport http --port 5435 --verbose

