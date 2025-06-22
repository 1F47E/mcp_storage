package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/mark3labs/mcp-go/server"
	"github.com/rs/zerolog/log"
)

func main() {
	// Load configuration
	cfg, err := LoadConfig()
	if err != nil {
		panic(fmt.Sprintf("Failed to load configuration: %v", err))
	}

	// Initialize adapter registry
	registry := NewAdapterRegistry()

	// Register database adapters
	postgresAdapter := NewPostgresAdapter(cfg.PostgresURL)
	if err := registry.Register(postgresAdapter); err != nil {
		log.Error().Err(err).Msg("Failed to register PostgreSQL adapter")
	}

	mysqlAdapter := NewMySQLAdapter(cfg.MySQLURL)
	if err := registry.Register(mysqlAdapter); err != nil {
		log.Error().Err(err).Msg("Failed to register MySQL adapter")
	}

	// Check if at least one adapter is registered
	if registry.IsEmpty() {
		panic("No database adapters configured. Please set at least one database connection in environment variables.")
	}

	// Create MCP server
	mcpServer := server.NewServer(
		"mcp-storage",
		"1.0.0",
		server.WithPrompts(),
		server.WithResources(),
	)

	// Register tools
	registerTools(mcpServer, registry)

	// Create Fiber app
	app := fiber.New(fiber.Config{
		ServerHeader:          "mcp-storage",
		DisableStartupMessage: false,
		AppName:               "MCP Storage Server",
		ReadTimeout:           30 * time.Second,
		WriteTimeout:          30 * time.Second,
		IdleTimeout:           120 * time.Second,
	})

	// Middleware
	app.Use(recover.New())
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*",
		AllowHeaders: "Origin, Content-Type, Accept, Authorization",
		AllowMethods: "GET, POST, OPTIONS",
	}))
	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} - ${method} ${path} - ${latency}\n",
	}))

	// Setup routes
	setupRoutes(app, mcpServer)

	// Graceful shutdown
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-c
		log.Info().Msg("Gracefully shutting down...")
		
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		// Close database connections
		if err := registry.Close(); err != nil {
			log.Error().Err(err).Msg("Error closing database connections")
		}

		// Shutdown Fiber
		if err := app.ShutdownWithContext(ctx); err != nil {
			log.Error().Err(err).Msg("Error shutting down server")
		}
	}()

	// Start server
	addr := fmt.Sprintf("%s:%s", cfg.Host, cfg.Port)
	log.Info().
		Str("address", addr).
		Strs("adapters", registry.List()).
		Int("tools", len(mcpServer.ListTools())).
		Msg("Starting MCP Storage Server")

	if err := app.Listen(addr); err != nil {
		log.Fatal().Err(err).Msg("Failed to start server")
	}
}