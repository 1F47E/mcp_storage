package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/rs/zerolog/log"
)

func main() {
	// Initialize logger first
	InitLogger()
	
	// Test debug logging
	log.Debug().Msg("=== DEBUG LOGGING TEST - This should appear if debug is enabled ===")

	l := log.With().Str("scope", "main").Logger()

	// Load configuration
	cfg, err := LoadConfig()
	if err != nil {
		panic(fmt.Sprintf("Failed to load configuration: %v", err))
	}

	// Initialize adapter registry
	adapterRegistry := NewAdapterRegistry()

	// Register database adapters
	postgresAdapter := NewPostgresAdapter(cfg.PostgresURL)
	if err := adapterRegistry.Register(postgresAdapter); err != nil {
		l.Error().Err(err).Msg("Failed to register PostgreSQL adapter")
	}

	mysqlAdapter := NewMySQLAdapter(cfg.MySQLURL)
	if err := adapterRegistry.Register(mysqlAdapter); err != nil {
		l.Error().Err(err).Msg("Failed to register MySQL adapter")
	}

	// Check if at least one adapter is registered
	if adapterRegistry.IsEmpty() {
		l.Warn().Msg("No database adapters configured. Only built-in tools will be available.")
	}

	// Create tool registry and register tools
	toolRegistry := NewToolRegistry()
	RegisterTools(toolRegistry, adapterRegistry)

	// Create JSON-RPC handler
	rpcHandler := NewJSONRPCHandler()

	// Register MCP methods
	registerMCPMethods(rpcHandler, toolRegistry)

	// Create MCP transport
	useSession := os.Getenv("MCP_USE_SESSION") == "true"
	transport := NewMCPTransport(rpcHandler, useSession)

	// Create Fiber app
	app := fiber.New(fiber.Config{
		ServerHeader:          "mcp-storage",
		DisableStartupMessage: false,
		AppName:               "MCP Storage Server",
		ReadTimeout:           30 * time.Second,
		WriteTimeout:          30 * time.Second,
		IdleTimeout:           120 * time.Second,
		JSONEncoder:           json.Marshal,
		JSONDecoder:           json.Unmarshal,
	})

	// Middleware
	app.Use(recover.New())
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*",
		AllowHeaders: "Origin, Content-Type, Accept, Authorization, Mcp-Session-Id",
		AllowMethods: "GET, POST, OPTIONS",
	}))

	// Conditional request logging
	if debugMode {
		app.Use(logger.New(logger.Config{
			Format: "[${time}] ${status} - ${method} ${path} - ${latency}\n",
		}))
	}

	// Setup routes
	transport.SetupRoutes(app)

	// Graceful shutdown
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-c
		l.Info().Msg("Gracefully shutting down...")

		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		// Close database connections
		if err := adapterRegistry.Close(); err != nil {
			l.Error().Err(err).Msg("Error closing database connections")
		}

		// Shutdown Fiber
		if err := app.ShutdownWithContext(ctx); err != nil {
			l.Error().Err(err).Msg("Error shutting down server")
		}
	}()

	// Start server
	addr := fmt.Sprintf("%s:%s", cfg.Host, cfg.Port)
	l.Info().
		Str("address", addr).
		Strs("adapters", adapterRegistry.List()).
		Int("tools", len(toolRegistry.ListTools())).
		Bool("session_management", useSession).
		Msg("Starting MCP Storage Server")

	if err := app.Listen(addr); err != nil {
		l.Fatal().Err(err).Msg("Failed to start server")
	}
}

// registerMCPMethods registers all MCP protocol methods
func registerMCPMethods(handler *JSONRPCHandler, toolRegistry *ToolRegistry) {
	l := log.With().Str("scope", "registerMCPMethods").Logger()

	// Initialize method
	handler.RegisterMethod("initialize", func(params json.RawMessage) (interface{}, error) {
		var req InitializeParams
		if err := json.Unmarshal(params, &req); err != nil {
			l.Error().Err(err).Str("params", string(params)).Msg("Failed to parse initialize params")
			return nil, NewRPCError(InvalidParams, "Invalid parameters", err.Error())
		}

		// Log initialize request details
		l.Debug().
			Str("client_protocol_version", req.ProtocolVersion).
			Str("server_protocol_version", ProtocolVersion).
			Str("client_name", req.ClientInfo.Name).
			Str("client_version", req.ClientInfo.Version).
			Interface("capabilities", req.Capabilities).
			Msg("=== INITIALIZE REQUEST DETAILS ===")

		// Validate protocol version
		if req.ProtocolVersion != ProtocolVersion {
			l.Warn().
				Str("client_protocol_version", req.ProtocolVersion).
				Str("server_protocol_version", ProtocolVersion).
				Msg("Protocol version mismatch")
			return nil, NewRPCError(InvalidParams, "Unsupported protocol version",
				fmt.Sprintf("Server supports %s, client requested %s", ProtocolVersion, req.ProtocolVersion))
		}

		// Build server capabilities
		capabilities := ServerCapabilities{
			Tools: &ToolsCapability{
				ListChanged: false,
			},
		}

		result := InitializeResult{
			ProtocolVersion: ProtocolVersion,
			Capabilities:    capabilities,
			ServerInfo: ServerInfo{
				Name:    "MCP Storage Server",
				Version: "1.0.0",
			},
		}

		l.Info().
			Str("client_name", req.ClientInfo.Name).
			Str("client_version", req.ClientInfo.Version).
			Msg("Client initialized")

		return result, nil
	})

	// Initialized notification
	handler.RegisterMethod("notifications/initialized", func(params json.RawMessage) (interface{}, error) {
		l.Debug().Msg("Client initialized notification received")
		return nil, nil
	})

	// Tools list method
	handler.RegisterMethod("tools/list", func(params json.RawMessage) (interface{}, error) {
		tools := toolRegistry.ListTools()
		return ListToolsResult{Tools: tools}, nil
	})

	// Tools call method
	handler.RegisterMethod("tools/call", func(params json.RawMessage) (interface{}, error) {
		var req CallToolParams
		if err := json.Unmarshal(params, &req); err != nil {
			return nil, NewRPCError(InvalidParams, "Invalid parameters", err.Error())
		}

		ctx := context.Background()
		result, err := toolRegistry.CallTool(ctx, req.Name, req.Arguments)
		if err != nil {
			// Return error as tool result
			return &CallToolResult{
				Content: []Content{
					TextContent{
						Type: "text",
						Text: fmt.Sprintf("Error: %v", err),
					},
				},
				IsError: true,
			}, nil
		}

		return result, nil
	})

	l.Info().Msg("MCP methods registered")
}
