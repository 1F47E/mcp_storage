.PHONY: server build run test-mcp lint clean docker-build docker-up docker-down docker-logs

# Build the Go server
build:
	@echo "Building Go server..."
	@go build -o mcp-storage .

# Run the server locally
run: build
	@echo "Starting MCP Storage Server on port 5435..."
	@./mcp-storage

# Run the server with debug mode
run-debug: build
	@echo "Starting MCP Storage Server in debug mode..."
	@DEBUG=1 ./mcp-storage

# Test MCP protocol with Python client
test-mcp:
	@echo "Testing MCP Storage Server..."
	@python3 test_client.py

# Test with debug output
test-mcp-debug:
	@echo "Testing MCP Storage Server with debug output..."
	@python3 test_client.py --debug

# Run linters
lint:
	@echo "Running Go linters..."
	@go vet ./...
	@go fmt ./...
	@golangci-lint run || echo "golangci-lint not installed, skipping"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -f mcp-storage
	@go clean

# Docker commands
docker-build:
	@echo "Building Docker image..."
	@docker-compose build

docker-up:
	@echo "Starting Docker containers..."
	@docker-compose up -d

docker-down:
	@echo "Stopping Docker containers..."
	@docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	@docker-compose logs -f mcp-storage

# Install Python test dependencies
test-deps:
	@echo "Installing Python test dependencies..."
	@pip install requests