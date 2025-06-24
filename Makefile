.PHONY: help build run run-debug test lint clean docker-build docker-run docker-stop docker-restart docker-down docker-logs

# Default target
.DEFAULT_GOAL := help

# Help documentation
help:
	@echo "MCP Storage Server - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make build          Build the Go server"
	@echo "  make run-local      Run server locally (no Docker)"
	@echo "  make run-debug      Run server with debug logging"
	@echo "  make test           Run tests with Python client"
	@echo "  make test-debug     Run tests with debug output"
	@echo "  make lint           Run Go linters"
	@echo "  make clean          Clean build artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  make run            Start server with Docker Compose (detached)"
	@echo "  make stop           Stop Docker containers"
	@echo "  make restart        Restart Docker containers"
	@echo "  make down           Stop and remove Docker containers"
	@echo "  make logs           Show Docker logs (follow mode)"
	@echo "  make ps             Show Docker container status"
	@echo ""
	@echo "Setup:"
	@echo "  make test-deps      Install Python test dependencies"

# Build the Go server
build:
	@echo "Building Go server..."
	@go build -o mcp-storage .

# Run the server locally (without Docker)
run-local: build
	@echo "Starting MCP Storage Server locally on port 5435..."
	@./mcp-storage

# Run the server with debug logging
run-debug: build
	@echo "Starting MCP Storage Server with debug logging..."
	@LOG_LEVEL=debug ./mcp-storage

# Docker: Run server with docker-compose
run:
	@echo "Starting MCP Storage Server with Docker..."
	@docker-compose up -d
	@echo "Server started. Use 'make logs' to view logs."

# Docker: Stop containers
stop:
	@echo "Stopping Docker containers..."
	@docker-compose stop

# Docker: Restart containers
restart:
	@echo "Restarting Docker containers..."
	@docker-compose restart
	@echo "Server restarted. Use 'make logs' to view logs."

# Docker: Stop and remove containers
down:
	@echo "Stopping and removing Docker containers..."
	@docker-compose down

# Docker: Show logs
logs:
	@echo "Showing Docker logs (Ctrl+C to exit)..."
	@docker-compose logs -f mcp-storage

# Docker: Show container status
ps:
	@docker-compose ps

# Docker: Build image
docker-build:
	@echo "Building Docker image..."
	@docker-compose build

# Test MCP protocol with Python client
test:
	@echo "Testing MCP Storage Server..."
	@python3 test_client.py

# Shorthand alias
test-mcp: test

# Test with debug output
test-debug:
	@echo "Testing MCP Storage Server with debug output..."
	@python3 test_client.py --debug

# Shorthand alias
test-mcp-debug: test-debug

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

# Install Python test dependencies
test-deps:
	@echo "Installing Python test dependencies..."
	@pip install requests

# Quick health check
health:
	@curl -s http://localhost:5435/health | jq . || echo "Server not responding"