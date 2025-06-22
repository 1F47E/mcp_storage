// --- File: cmd/server/main.go ---
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io" // Needed for io.WriteString
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	flogger "github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/google/uuid"

	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server" // Keep using the core server logic

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/rs/zerolog/pkgerrors"
	// NOTE: No need for fasthttp import when using bufio.Writer directly
)

const (
	ServerName            = "mcp-go-tool-server-custom-sse"
	ServerVersion         = "1.0.3" // Incremented version
	DefaultPort           = 8008
	DefaultHost           = "127.0.0.1"
	DefaultBaseURLPattern = "http://%s:%d"
	ssePath               = "/sse"
	messagePath           = "/message"
	KeepAliveInterval     = 15 * time.Second // Send keep-alive slightly more often
)

// --- Custom SSE Session Management ---

// sseSession (remains the same)
type sseSession struct {
	sessionID           string
	eventQueue          chan string
	notificationChannel chan mcp.JSONRPCNotification
	done                chan struct{}
	initialized         atomic.Bool
	mu                  sync.Mutex
}

func (s *sseSession) SessionID() string {
	return s.sessionID
}

func (s *sseSession) NotificationChannel() chan<- mcp.JSONRPCNotification {
	return s.notificationChannel
}

func (s *sseSession) Initialize() {
	s.initialized.Store(true)
	log.Debug().Str("session_id", s.sessionID).Msg("Session marked as initialized")
}

func (s *sseSession) Initialized() bool {
	return s.initialized.Load()
}

func (s *sseSession) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	select {
	case <-s.done:
	default:
		close(s.done)
		log.Debug().Str("session_id", s.sessionID).Msg("Session closed signal sent")
	}
}

func (s *sseSession) sendEvent(event string) bool {
	select {
	case <-s.done:
		log.Warn().Str("session_id", s.sessionID).Msg("Attempted to send event to closed session")
		return false
	// Use non-blocking send with timeout to prevent deadlocks if queue is full and writer is blocked
	case s.eventQueue <- event:
		log.Trace().Str("session_id", s.sessionID).Str("event_prefix", strings.Split(event, "\n")[0]).Msg("Event queued for sending")
		return true
	default:
		log.Warn().Str("session_id", s.sessionID).Msg("Event queue full, dropping event")
		// Optional: Add a small timeout to wait if queue is full
		// select {
		// case s.eventQueue <- event:
		//  log.Trace().Str("session_id", s.sessionID).Msg("Event queued after brief wait")
		// 	return true
		// case <-time.After(50 * time.Millisecond):
		// 	log.Warn().Str("session_id", s.sessionID).Msg("Event queue full, dropping event after timeout")
		// 	return false
		// case <-s.done:
		// 	return false
		// }
		return false
	}
}

var sessions = sync.Map{}

// --- Tool Implementation (remains the same) ---
func handleRandomUint64Tool(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	logger := log.Ctx(ctx)
	if logger == nil || logger.GetLevel() == zerolog.Disabled {
		logger = &log.Logger
	}
	logger.Debug().Str("tool_name", request.Params.Name).Msg("Handling tool call")
	randomValue := rand.Uint64()
	logger.Info().Str("tool_name", request.Params.Name).Uint64("value", randomValue).Msg("Generated random value")
	result := mcp.NewToolResultText(fmt.Sprintf("%d", randomValue))
	return result, nil
}

// --- Configuration and Setup (remains the same) ---
func setupLogger(debugLevelStr string) {
	level := zerolog.InfoLevel
	if debugLevelStr != "" {
		if i, err := strconv.Atoi(debugLevelStr); err == nil {
			switch i {
			case 0:
				level = zerolog.InfoLevel
			case 1:
				level = zerolog.DebugLevel
			default:
				level = zerolog.TraceLevel
			}
			log.Info().Int("numeric_level", i).Str("zerolog_level", level.String()).Msg("Parsed DEBUG level")
		} else {
			log.Warn().Str("value", debugLevelStr).Msg("Invalid DEBUG level format, using Info")
		}
	}
	zerolog.SetGlobalLevel(level)
	zerolog.TimeFieldFormat = time.RFC3339
	zerolog.ErrorStackMarshaler = pkgerrors.MarshalStack
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr, TimeFormat: time.RFC3339}).With().Caller().Logger()
	log.Info().Str("level", level.String()).Msg("Logger level set")
}

// --- Helper to create JSON-RPC Error Response ---
func createJSONRPCError(id interface{}, code int, message string, data interface{}) mcp.JSONRPCError {
	errObj := struct {
		Code    int         `json:"code"`
		Message string      `json:"message"`
		Data    interface{} `json:"data,omitempty"`
	}{
		Code:    code,
		Message: message,
		Data:    data,
	}
	return mcp.JSONRPCError{
		JSONRPC: mcp.JSONRPC_VERSION,
		ID:      id, // Can be nil for parse errors before ID is known
		Error:   errObj,
	}
}

// --- Main Server Logic ---
func main() {
	rand.New(rand.NewSource(time.Now().UnixNano()))
	setupLogger(os.Getenv("DEBUG"))

	// --- Configuration (remains the same) ---
	port := DefaultPort
	if portEnv := os.Getenv("PORT"); portEnv != "" {
		if p, err := strconv.Atoi(portEnv); err == nil && p > 0 && p < 65536 {
			port = p
		} else {
			log.Warn().Str("value", portEnv).Int("default", DefaultPort).Msg("Invalid PORT environment variable, using default")
		}
	}
	host := DefaultHost
	if hostEnv := os.Getenv("HOST"); hostEnv != "" {
		host = hostEnv
		log.Info().Str("host", host).Msg("Using HOST from env")
	} else {
		log.Info().Str("host", host).Msg("Using default HOST")
	}
	listenAddr := fmt.Sprintf("%s:%d", host, port)

	baseURL := os.Getenv("MCP_BASE_URL")
	if baseURL == "" {
		baseURL = fmt.Sprintf(DefaultBaseURLPattern, host, port)
		if host == "0.0.0.0" {
			localhostURL := fmt.Sprintf(DefaultBaseURLPattern, "127.0.0.1", port)
			log.Warn().Str("configured_host", host).Str("default_base_url", baseURL).Str("recommended_base_url", localhostURL).Msg("Default BaseURL uses 0.0.0.0. Clients might need to connect via 127.0.0.1. Consider setting MCP_BASE_URL.")
			baseURL = localhostURL
			log.Info().Str("url", baseURL).Msg("Adjusted default MCP Base URL for client")
		} else {
			log.Info().Str("url", baseURL).Msg("Using default MCP Base URL")
		}
	} else {
		baseURL = strings.TrimSuffix(baseURL, "/")
		if !strings.HasPrefix(baseURL, "http") {
			log.Warn().Str("url", baseURL).Msg("MCP_BASE_URL might be invalid (missing http:// or https://)")
		}
		log.Info().Str("url", baseURL).Msg("Using MCP Base URL from env")
	}

	// --- MCP Server Core Setup ---
	log.Info().Msg("Initializing MCP Server Core...")
	mcpServer := mcpserver.NewMCPServer(
		ServerName,
		ServerVersion,
		mcpserver.WithToolCapabilities(true),
	)
	randomTool := mcp.NewTool("random_uint64", mcp.WithDescription("Generate a random uint64."))
	mcpServer.AddTool(randomTool, handleRandomUint64Tool)
	log.Info().Str("tool_name", randomTool.Name).Msg("Registered tool with MCP Core")

	// --- Fiber Web Server Setup ---
	log.Info().Msg("Initializing Fiber Web Server...")
	app := fiber.New(fiber.Config{
		AppName:               ServerName + " v" + ServerVersion,
		DisableStartupMessage: true,
	})
	app.Hooks().OnListen(func(listenData fiber.ListenData) error {
		log.Info().Str("host", listenData.Host).Str("port", listenData.Port).Bool("tls", listenData.TLS).Msg("Fiber server listener is ready")
		return nil
	})

	// --- Fiber Middleware ---
	app.Use(recover.New(recover.Config{EnableStackTrace: true}))
	app.Use(flogger.New(flogger.Config{
		Format: "[FIBER] ${time} ${status} ${latency} ${method} ${path} ReqIP=${ip} Error='${error}'\n",
		Output: os.Stderr,
	}))
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*",
		AllowHeaders: "Origin, Content-Type, Accept, Cache-Control, Connection, Access-Control-Allow-Origin, Authorization, X-Requested-With",
		AllowMethods: "GET, POST, OPTIONS",
	}))

	// --- Custom Fiber Route Handlers ---

	// Handles the initial SSE connection request (GET /sse)
	app.Get(ssePath, func(c *fiber.Ctx) error {
		c.Set("Content-Type", "text/event-stream")
		c.Set("Cache-Control", "no-cache")
		c.Set("Connection", "keep-alive")
		c.Set("Access-Control-Allow-Origin", "*")

		sessionID := uuid.NewString()
		session := &sseSession{
			sessionID:           sessionID,
			eventQueue:          make(chan string, 100),
			notificationChannel: make(chan mcp.JSONRPCNotification, 100),
			done:                make(chan struct{}),
		}
		log.Info().Str("session_id", sessionID).Str("remote_ip", c.IP()).Msg("SSE connection establishing...")

		// Store session *before* registering to prevent race condition on immediate disconnect
		sessions.Store(sessionID, session)

		if err := mcpServer.RegisterSession(session); err != nil {
			log.Error().Err(err).Str("session_id", sessionID).Msg("Failed to register session with MCP core")
			sessions.Delete(sessionID) // Clean up if registration fails
			return fiber.NewError(http.StatusInternalServerError, "Failed to register session")
		}
		log.Debug().Str("session_id", sessionID).Msg("Session registered with MCP core")

		// Use a context for this specific connection derived from the request context
		connCtx := c.UserContext()
		clientDisconnected := connCtx.Done() // Channel indicating client disconnect

		// Start notification listener goroutine
		go func() {
			log.Debug().Str("session_id", sessionID).Msg("Starting notification listener goroutine")
			defer log.Debug().Str("session_id", sessionID).Msg("Notification listener stopped")
			for {
				select {
				case <-session.done: // Closed by server shutdown or handler error
					return
				case <-clientDisconnected: // Closed by client disconnect
					return
				case notification := <-session.notificationChannel:
					eventData, err := json.Marshal(notification)
					if err != nil {
						log.Error().Err(err).Str("session_id", sessionID).Msg("Failed to marshal notification")
						continue
					}
					sseFormattedEvent := fmt.Sprintf("event: message\ndata: %s\n\n", eventData)
					if !session.sendEvent(sseFormattedEvent) {
						log.Warn().Str("session_id", sessionID).Msg("Failed to queue notification event (session might be closing)")
						// No need to return here, just log and continue trying or wait for closure
					}
				}
			}
		}()

		// Calculate the message endpoint URL
		messageEndpointURL := fmt.Sprintf("%s%s?sessionId=%s", baseURL, messagePath, sessionID)

		// *** CRITICAL FIX: SetBodyStreamWriter must block ***
		// We use the callback to manage the long-lived connection.
		// Fiber will keep the connection open as long as this callback doesn't return.
		c.Context().SetBodyStreamWriter(func(w *bufio.Writer) { // Correct signature: func(*bufio.Writer)
			log.Info().Str("session_id", sessionID).Msg("SSE Stream Writer started")

			// Send the initial endpoint event
			log.Info().Str("session_id", sessionID).Str("endpoint", messageEndpointURL).Msg("Sending endpoint event to client")
			_, writeErr := fmt.Fprintf(w, "event: endpoint\ndata: %s\n\n", messageEndpointURL)
			if writeErr != nil {
				log.Error().Err(writeErr).Str("session_id", sessionID).Msg("Error writing endpoint event")
				// Cannot return error here, signal closure
				session.Close()
				return // Exit the stream writer function
			}
			flushErr := w.Flush()
			if flushErr != nil {
				log.Error().Err(flushErr).Str("session_id", sessionID).Msg("Error flushing endpoint event")
				session.Close()
				return // Exit the stream writer function
			}
			log.Debug().Str("session_id", sessionID).Msg("Endpoint event sent and flushed")

			// Now handle the long-lived connection
			keepAliveTicker := time.NewTicker(KeepAliveInterval)
			defer keepAliveTicker.Stop()

			log.Debug().Str("session_id", sessionID).Msg("Starting SSE event write loop")
			for {
				select {
				case <-session.done: // Closed by server shutdown or another error
					log.Debug().Str("session_id", sessionID).Msg("SSE writer loop exiting (session done signaled)")
					return // Exit the stream writer function
				case <-clientDisconnected: // Client closed connection
					log.Info().Str("session_id", sessionID).Msg("Client disconnected")
					session.Close() // Ensure session state is cleaned up
					return          // Exit the stream writer function

				case event, ok := <-session.eventQueue:
					if !ok { // Channel closed (shouldn't happen with current logic, but defensive)
						log.Warn().Str("session_id", sessionID).Msg("Event queue channel closed unexpectedly")
						session.Close()
						return
					}
					log.Trace().Str("session_id", sessionID).Str("event", strings.TrimSpace(event)).Msg("Writing event to client")
					_, writeErr := io.WriteString(w, event) // Use io.WriteString for efficiency
					if writeErr != nil {
						log.Error().Err(writeErr).Str("session_id", sessionID).Msg("Error writing event to client stream")
						session.Close()
						return
					}
					flushErr := w.Flush()
					if flushErr != nil {
						log.Error().Err(flushErr).Str("session_id", sessionID).Msg("Error flushing client stream")
						session.Close()
						return
					}
					log.Trace().Str("session_id", sessionID).Msg("Event flushed")

				case <-keepAliveTicker.C:
					log.Trace().Str("session_id", sessionID).Msg("Sending keep-alive comment")
					_, writeErr := io.WriteString(w, ": keep-alive\n\n")
					if writeErr != nil {
						log.Error().Err(writeErr).Str("session_id", sessionID).Msg("Error writing keep-alive")
						session.Close()
						return
					}
					flushErr := w.Flush()
					if flushErr != nil {
						log.Error().Err(flushErr).Str("session_id", sessionID).Msg("Error flushing keep-alive")
						session.Close()
						return
					}
					log.Trace().Str("session_id", sessionID).Msg("Keep-alive flushed")
				}
			}
		}) // End of SetBodyStreamWriter callback

		// Log if SetBodyStreamWriter itself returned an error (rare)
		// if err != nil {
		// 	log.Error().Err(err).Str("session_id", sessionID).Msg("SetBodyStreamWriter returned an error")
		// }

		// Crucially, DO NOT return anything here for Fiber streaming handlers.
		// Fiber keeps the handler alive based on the stream writer.
		log.Debug().Str("session_id", sessionID).Msg("handleSSEConnection function is finishing (stream writer continues)")
		return nil
	})

	// Handles incoming MCP messages (POST /message)
	app.Post(messagePath, func(c *fiber.Ctx) error {
		sessionID := c.Query("sessionId")
		if sessionID == "" {
			log.Error().Str("remote_ip", c.IP()).Msg("Missing sessionId in message request")
			errResp := createJSONRPCError(nil, mcp.INVALID_PARAMS, "Missing sessionId query parameter", nil)
			return c.Status(http.StatusBadRequest).JSON(errResp)
		}

		log.Debug().Str("session_id", sessionID).Str("remote_ip", c.IP()).Msg("Received message POST")

		sessionI, ok := sessions.Load(sessionID)
		if !ok {
			log.Error().Str("session_id", sessionID).Msg("Invalid or expired session ID")
			errResp := createJSONRPCError(nil, mcp.INVALID_PARAMS, "Invalid session ID", nil) // ID might not be known yet
			return c.Status(http.StatusBadRequest).JSON(errResp)
		}
		session := sessionI.(*sseSession)

		// Check if session is already closed
		select {
		case <-session.done:
			log.Error().Str("session_id", sessionID).Msg("Received message for already closed session")
			errResp := createJSONRPCError(nil, mcp.INVALID_PARAMS, "Session closed or invalid", nil)
			return c.Status(http.StatusBadRequest).JSON(errResp)
		default:
			// Session is active
		}

		// Parse message as raw JSON
		var rawMessage json.RawMessage
		if err := c.BodyParser(&rawMessage); err != nil {
			rawMessage = json.RawMessage(c.Body())
			if !json.Valid(rawMessage) {
				log.Error().Err(err).Str("session_id", sessionID).Bytes("body", c.Body()).Msg("Failed to parse request body")
				errResp := createJSONRPCError(nil, mcp.PARSE_ERROR, "Parse error: Invalid JSON", nil)
				return c.Status(http.StatusBadRequest).JSON(errResp)
			}
			log.Warn().Str("session_id", sessionID).Msg("Fiber BodyParser failed, using raw body")
		}

		// --- Attempt to extract request ID for error responses ---
		var baseReq struct {
			ID json.RawMessage `json:"id"`
		}
		// Ignore unmarshal error here, ID might be null or absent
		_ = json.Unmarshal(rawMessage, &baseReq)
		var requestID any = baseReq.ID // Keep as json.RawMessage or nil
		if len(baseReq.ID) > 0 && string(baseReq.ID) == "null" {
			requestID = nil // Treat JSON null ID as nil
		}
		// ---

		// Create context with session info
		mcpCtx := mcpServer.WithContext(c.UserContext(), session)

		// Process message through MCPServer core
		responseMsg := mcpServer.HandleMessage(mcpCtx, rawMessage)

		// Queue response if it's not a notification
		if responseMsg != nil {
			responseBytes, err := json.Marshal(responseMsg)
			if err != nil {
				log.Error().Err(err).Str("session_id", sessionID).Msg("Failed to marshal MCP response")
				errResp := createJSONRPCError(requestID, mcp.INTERNAL_ERROR, "Failed to marshal response", nil)
				return c.Status(http.StatusInternalServerError).JSON(errResp)
			}
			sseFormattedEvent := fmt.Sprintf("event: message\ndata: %s\n\n", responseBytes)
			if !session.sendEvent(sseFormattedEvent) {
				log.Warn().Str("session_id", sessionID).Msg("Failed to queue MCP response event for SSE")
			}
		}

		// Always send 202 Accepted for the POST request
		return c.SendStatus(http.StatusAccepted)
	})

	// OPTIONS handlers (remain the same)
	log.Info().Msgf("Mounting OPTIONS handlers for CORS preflight on '%s' and '%s'", ssePath, messagePath)
	app.Options(ssePath, func(c *fiber.Ctx) error {
		log.Trace().Str("path", ssePath).Msg("Responding to OPTIONS request (CORS preflight)")
		return c.SendStatus(fiber.StatusNoContent)
	})
	app.Options(messagePath, func(c *fiber.Ctx) error {
		log.Trace().Str("path", messagePath).Msg("Responding to OPTIONS request (CORS preflight)")
		return c.SendStatus(fiber.StatusNoContent)
	})

	// --- Graceful Shutdown Setup ---
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	_, serverCancel := context.WithCancel(context.Background()) // Renamed to avoid conflict

	// --- Start Server ---
	go func() {
		log.Info().Str("address", listenAddr).Msg("Attempting to start Fiber server...")
		if err := app.Listen(listenAddr); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatal().Err(err).Msg("Fiber server Listen failed") // Use Fatal to exit if listen fails critically
		}
	}()

	// --- Wait for Shutdown Signal ---
	sig := <-stop
	log.Warn().Str("signal", sig.String()).Msg("Interrupt signal received, initiating shutdown...")
	serverCancel() // Signal context cancellation

	// --- Close active SSE sessions ---
	log.Info().Msg("Closing active SSE sessions...")
	sessions.Range(func(key, value interface{}) bool {
		if session, ok := value.(*sseSession); ok {
			log.Debug().Str("session_id", session.sessionID).Msg("Closing session via shutdown")
			session.Close()
		}
		return true // Continue iterating
	})
	log.Info().Msg("Finished closing SSE sessions.")

	// --- Perform Fiber Shutdown ---
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	log.Info().Msg("Shutting down Fiber server...")
	if err := app.ShutdownWithContext(shutdownCtx); err != nil {
		log.Error().Err(err).Msg("Error during Fiber server shutdown")
	} else {
		log.Info().Msg("Fiber server stopped.")
	}

	// No need to call sseServer.Shutdown() as we are managing sessions directly

	log.Info().Msg("Server shutdown complete.")
}
