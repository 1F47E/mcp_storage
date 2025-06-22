package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

var debugMode bool

// InitLogger initializes the global logger based on environment variables
func InitLogger() {
	// Check DEBUG environment variable
	debugEnv := os.Getenv("DEBUG")
	debugMode = debugEnv == "1" || debugEnv == "true"

	// Set log level based on LOG_LEVEL env var or DEBUG mode
	level := zerolog.InfoLevel
	if debugMode {
		level = zerolog.DebugLevel
	}

	// Allow LOG_LEVEL to override
	if levelStr := os.Getenv("LOG_LEVEL"); levelStr != "" {
		switch levelStr {
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
		}
	}

	zerolog.SetGlobalLevel(level)

	// Configure console output
	output := zerolog.ConsoleWriter{
		Out:        os.Stderr,
		TimeFormat: "2006-01-02T15:04:05.000Z07:00",
	}
	
	// Enable all log levels in console writer
	output.FormatLevel = func(i interface{}) string {
		var levelStr string
		if ll, ok := i.(string); ok {
			switch ll {
			case "debug":
				levelStr = "DBG"
			case "info":
				levelStr = "INF"
			case "warn":
				levelStr = "WRN"
			case "error":
				levelStr = "ERR"
			default:
				levelStr = strings.ToUpper(ll)
			}
		}
		return fmt.Sprintf("\x1b[%dm%s\x1b[0m", 90, levelStr)
	}
	
	log.Logger = log.Output(output).With().Caller().Logger()

	log.Info().
		Str("level", level.String()).
		Bool("debug_mode", debugMode).
		Msg("Logger initialized")
}

// IsDebugMode returns whether debug mode is enabled
func IsDebugMode() bool {
	return debugMode
}

// ParseBool safely parses a string to bool
func ParseBool(s string) bool {
	b, _ := strconv.ParseBool(s)
	return b
}
