package main

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
)

// MCPTransport handles HTTP transport for MCP protocol
type MCPTransport struct {
	handler        *JSONRPCHandler
	sessionManager *SessionManager
	useSession     bool
}

// NewMCPTransport creates a new MCP transport
func NewMCPTransport(handler *JSONRPCHandler, useSession bool) *MCPTransport {
	var sm *SessionManager
	if useSession {
		// 30 minute session timeout
		sm = NewSessionManager(30 * time.Minute)
	}

	return &MCPTransport{
		handler:        handler,
		sessionManager: sm,
		useSession:     useSession,
	}
}

// SetupRoutes configures HTTP routes for the MCP server
func (t *MCPTransport) SetupRoutes(app *fiber.App) {
	// Health check endpoint
	app.Get("/health", t.handleHealth)

	// Main MCP endpoint - handles all MCP protocol messages
	app.Post("/", t.handleMCPRequest)

	// OAuth mock endpoints for Claude Code compatibility
	t.setupOAuthMockEndpoints(app)
}

// handleHealth handles health check requests
func (t *MCPTransport) handleHealth(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{
		"status":  "healthy",
		"time":    time.Now().UTC().Format(time.RFC3339),
		"version": ProtocolVersion,
	})
}

// handleMCPRequest handles MCP protocol requests
func (t *MCPTransport) handleMCPRequest(c *fiber.Ctx) error {
	l := log.With().Str("scope", "handleMCPRequest").Logger()

	// Set content type
	c.Set("Content-Type", "application/json")

	// Log request in debug mode
	if debugMode {
		// Collect all headers
		headers := make(map[string]string)
		c.Request().Header.VisitAll(func(key, value []byte) {
			headers[string(key)] = string(value)
		})
		
		// Pretty print body if JSON
		var prettyBody string
		var jsonData interface{}
		if err := json.Unmarshal(c.Body(), &jsonData); err == nil {
			if prettyBytes, err := json.MarshalIndent(jsonData, "", "  "); err == nil {
				prettyBody = string(prettyBytes)
			} else {
				prettyBody = string(c.Body())
			}
		} else {
			prettyBody = string(c.Body())
		}
		
		l.Debug().
			Str("method", c.Method()).
			Str("path", c.Path()).
			Str("url", c.OriginalURL()).
			Interface("headers", headers).
			Str("body", prettyBody).
			Msg("=== INCOMING HTTP REQUEST ===")
	}

	// Handle session if enabled
	var session *Session
	if t.useSession {
		sessionID := c.Get("Mcp-Session-Id")
		if sessionID != "" {
			var exists bool
			session, exists = t.sessionManager.GetSession(sessionID)
			if !exists {
				l.Warn().Str("session_id", sessionID).Msg("Invalid session ID")
			}
		}
	}

	// Process the request
	requestBody := c.Body()

	// Parse request to check if it's an initialize request
	var req JSONRPCRequest
	if err := json.Unmarshal(requestBody, &req); err == nil && req.Method == "initialize" {
		// Handle initialize specially to create/return session
		return t.handleInitialize(c, &req, session)
	}

	// For other requests, check if session is required and initialized
	if t.useSession && session != nil && !session.IsInitialized() && !strings.HasPrefix(req.Method, "notifications/") {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"error": "Session not initialized",
		})
	}

	// Process request through JSON-RPC handler
	response := t.handler.HandleRequest(requestBody)

	// If no response (notification), return 204 No Content
	if response == nil {
		return c.SendStatus(fiber.StatusNoContent)
	}

	// Log response in debug mode
	if debugMode {
		// Pretty print response if JSON
		var prettyResponse string
		var jsonData interface{}
		if err := json.Unmarshal(response, &jsonData); err == nil {
			if prettyBytes, err := json.MarshalIndent(jsonData, "", "  "); err == nil {
				prettyResponse = string(prettyBytes)
			} else {
				prettyResponse = string(response)
			}
		} else {
			prettyResponse = string(response)
		}
		
		l.Debug().
			Str("response", prettyResponse).
			Msg("=== OUTGOING HTTP RESPONSE ===")
	}

	return c.Send(response)
}

// handleInitialize handles the initialize request specially
func (t *MCPTransport) handleInitialize(c *fiber.Ctx, req *JSONRPCRequest, session *Session) error {
	l := log.With().Str("scope", "handleInitialize").Logger()

	// Process through handler
	response := t.handler.HandleRequest(c.Body())

	// Parse response to check if successful
	var resp JSONRPCResponse
	if err := json.Unmarshal(response, &resp); err == nil && resp.Error == nil {
		// Initialize was successful
		if t.useSession {
			// Create new session if none exists
			if session == nil {
				session = t.sessionManager.CreateSession()
				// Add session ID to response header
				c.Set("Mcp-Session-Id", session.ID)
			}

			// Mark session as initialized
			var params InitializeParams
			if err := json.Unmarshal(req.Params, &params); err == nil {
				session.MarkInitialized(&params.ClientInfo)
			}

			l.Info().
				Str("session_id", session.ID).
				Str("client_name", session.ClientInfo.Name).
				Str("client_version", session.ClientInfo.Version).
				Msg("Session initialized")
		}
	}

	return c.Send(response)
}

// setupOAuthMockEndpoints sets up mock OAuth endpoints for Claude Code compatibility
func (t *MCPTransport) setupOAuthMockEndpoints(app *fiber.App) {
	l := log.With().Str("scope", "setupOAuthMockEndpoints").Logger()

	// OAuth discovery endpoint
	app.Get("/.well-known/oauth-authorization-server", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"issuer":                           fmt.Sprintf("http://%s", c.Hostname()),
			"authorization_endpoint":           fmt.Sprintf("http://%s/authorize", c.Hostname()),
			"token_endpoint":                   fmt.Sprintf("http://%s/token", c.Hostname()),
			"registration_endpoint":            fmt.Sprintf("http://%s/register", c.Hostname()),
			"response_types_supported":         []string{"code"},
			"grant_types_supported":            []string{"authorization_code"},
			"code_challenge_methods_supported": []string{"S256"},
		})
	})

	// Client registration endpoint
	app.Post("/register", func(c *fiber.Ctx) error {
		var body map[string]interface{}
		if err := c.BodyParser(&body); err != nil {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
				"error": "Invalid request body",
			})
		}

		clientID := uuid.New().String()
		clientSecret := uuid.New().String()

		return c.JSON(fiber.Map{
			"client_id":                clientID,
			"client_secret":            clientSecret,
			"client_id_issued_at":      time.Now().Unix(),
			"client_secret_expires_at": 0,
			"redirect_uris":            body["redirect_uris"],
			"grant_types":              []string{"authorization_code"},
			"response_types":           []string{"code"},
			"client_name":              body["client_name"],
		})
	})

	// Authorization endpoint
	app.Get("/authorize", func(c *fiber.Ctx) error {
		redirectURI := c.Query("redirect_uri")
		state := c.Query("state")

		if redirectURI == "" {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
				"error": "redirect_uri is required",
			})
		}

		// Generate a mock authorization code
		code := uuid.New().String()

		// Build redirect URL with code and state
		redirectURL := fmt.Sprintf("%s?code=%s", redirectURI, code)
		if state != "" {
			redirectURL = fmt.Sprintf("%s&state=%s", redirectURL, state)
		}

		return c.Redirect(redirectURL)
	})

	// Token endpoint
	app.Post("/token", func(c *fiber.Ctx) error {
		var body map[string]string
		if err := c.BodyParser(&body); err != nil {
			// Try form parsing
			body = make(map[string]string)
			body["grant_type"] = c.FormValue("grant_type")
			body["code"] = c.FormValue("code")
			body["redirect_uri"] = c.FormValue("redirect_uri")
			body["client_id"] = c.FormValue("client_id")
			body["client_secret"] = c.FormValue("client_secret")
			body["code_verifier"] = c.FormValue("code_verifier")
		}

		if body["grant_type"] != "authorization_code" {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
				"error": "unsupported_grant_type",
			})
		}

		// Generate mock tokens
		accessToken := uuid.New().String()

		return c.JSON(fiber.Map{
			"access_token": accessToken,
			"token_type":   "Bearer",
			"expires_in":   3600,
		})
	})

	l.Info().Msg("OAuth mock endpoints configured")
}
