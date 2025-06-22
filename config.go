package main

import (
	"os"

	"github.com/joho/godotenv"
	"github.com/rs/zerolog/log"
)

type Config struct {
	// Server settings
	Port     string
	Host     string
	LogLevel string

	// Database configurations
	PostgresURL string
	MySQLURL    string

	// Future adapters
	RedisURL   string
	MongoDBURL string
}

// LoadConfig loads configuration from environment variables
func LoadConfig() (*Config, error) {
	// Load .env file if it exists
	if err := godotenv.Load(); err != nil {
		log.Debug().Err(err).Msg("No .env file found, using environment variables")
	}

	cfg := &Config{
		Port:        getEnv("PORT", "5435"),
		Host:        getEnv("HOST", "0.0.0.0"),
		LogLevel:    getEnv("LOG_LEVEL", "info"),
		PostgresURL: os.Getenv("POSTGRES_URL"),
		MySQLURL:    os.Getenv("MYSQL_URL"),
		RedisURL:    os.Getenv("REDIS_URL"),
		MongoDBURL:  os.Getenv("MONGODB_URL"),
	}

	// Log adapter configuration
	if !cfg.HasAnyAdapter() {
		log.Warn().Msg("No database adapters configured. Only built-in tools will be available.")
	}

	log.Info().
		Bool("postgres", cfg.PostgresURL != "").
		Bool("mysql", cfg.MySQLURL != "").
		Bool("redis", cfg.RedisURL != "").
		Bool("mongodb", cfg.MongoDBURL != "").
		Msg("Configuration loaded")

	return cfg, nil
}

// HasAnyAdapter checks if at least one database adapter is configured
func (c *Config) HasAnyAdapter() bool {
	return c.PostgresURL != "" || c.MySQLURL != "" || c.RedisURL != "" || c.MongoDBURL != ""
}

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
