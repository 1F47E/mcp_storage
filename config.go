package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/joho/godotenv"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/rs/zerolog/pkgerrors"
)

type Config struct {
	// Server settings
	Port     string
	Host     string
	LogLevel string

	// Database configurations
	PostgresURL string
	MySQLDSN    string

	// Future adapters
	RedisURL   string
	MongoDBURI string
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
		MySQLDSN:    os.Getenv("MYSQL_DSN"),
		RedisURL:    os.Getenv("REDIS_URL"),
		MongoDBURI:  os.Getenv("MONGODB_URI"),
	}

	// Setup logger
	setupLogger(cfg.LogLevel)

	// Validate at least one adapter is configured
	if !cfg.HasAnyAdapter() {
		return nil, fmt.Errorf("no database adapters configured. Set at least one of: POSTGRES_URL, MYSQL_DSN")
	}

	log.Info().
		Bool("postgres", cfg.PostgresURL != "").
		Bool("mysql", cfg.MySQLDSN != "").
		Bool("redis", cfg.RedisURL != "").
		Bool("mongodb", cfg.MongoDBURI != "").
		Msg("Configuration loaded")

	return cfg, nil
}

// HasAnyAdapter checks if at least one database adapter is configured
func (c *Config) HasAnyAdapter() bool {
	return c.PostgresURL != "" || c.MySQLDSN != "" || c.RedisURL != "" || c.MongoDBURI != ""
}

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// setupLogger configures the global logger
func setupLogger(levelStr string) {
	// Configure time format and stack marshaler
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	zerolog.ErrorStackMarshaler = pkgerrors.MarshalStack

	// Parse log level
	level := zerolog.InfoLevel
	switch strings.ToLower(levelStr) {
	case "trace":
		level = zerolog.TraceLevel
	case "debug":
		level = zerolog.DebugLevel
	case "info":
		level = zerolog.InfoLevel
	case "warn", "warning":
		level = zerolog.WarnLevel
	case "error":
		level = zerolog.ErrorLevel
	case "fatal":
		level = zerolog.FatalLevel
	case "panic":
		level = zerolog.PanicLevel
	default:
		log.Warn().Str("level", levelStr).Msg("Unknown log level, using info")
	}

	zerolog.SetGlobalLevel(level)

	// Configure console output
	log.Logger = log.Output(zerolog.ConsoleWriter{
		Out:        os.Stderr,
		TimeFormat: "2006-01-02T15:04:05.000Z07:00",
	}).With().Caller().Logger()

	log.Info().Str("level", level.String()).Msg("Logger initialized")
}