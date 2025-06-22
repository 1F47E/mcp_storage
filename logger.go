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
	// Set log level based on LOG_LEVEL env var
	level := zerolog.InfoLevel
	levelStr := os.Getenv("LOG_LEVEL")
	
	switch strings.ToLower(levelStr) {
	case "trace":
		level = zerolog.TraceLevel
		debugMode = true
	case "debug":
		level = zerolog.DebugLevel
		debugMode = true
	case "info":
		level = zerolog.InfoLevel
		debugMode = false
	case "warn", "warning":
		level = zerolog.WarnLevel
		debugMode = false
	case "error":
		level = zerolog.ErrorLevel
		debugMode = false
	case "fatal":
		level = zerolog.FatalLevel
		debugMode = false
	case "panic":
		level = zerolog.PanicLevel
		debugMode = false
	default:
		// Default to info level
		level = zerolog.InfoLevel
		debugMode = false
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
