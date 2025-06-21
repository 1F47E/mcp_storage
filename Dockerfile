# Use the official Go image as build environment
FROM golang:1.21-alpine AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apk add --no-cache git

# Copy go mod files first (for better Docker layer caching)
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY server.go ./

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o server server.go

# Use a minimal alpine image for the final container
FROM alpine:latest

# Install ca-certificates for HTTPS requests (if needed)
RUN apk --no-cache add ca-certificates

# Create a non-root user
RUN adduser -D -s /bin/sh mcpuser

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /app/server .

# Change ownership of the app directory
RUN chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Expose the default port
EXPOSE 8008

# Set environment variables for Docker networking
ENV HOST=0.0.0.0
ENV PORT=8008

# Run the server
CMD ["./server"] 