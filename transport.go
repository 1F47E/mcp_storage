package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"github.com/mark3labs/mcp-go/server"
	"github.com/rs/zerolog/log"
)

func setupRoutes(app *fiber.App, mcpServer *server.MCPServer) {
	// Health check endpoint
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status": "healthy",
			"time":   time.Now().UTC().Format(time.RFC3339),
		})
	})

	// Main MCP endpoint - handles all MCP protocol messages
	app.Post("/", func(c *fiber.Ctx) error {
		c.Set("Content-Type", "application/json")

		var request map[string]interface{}
		if err := json.Unmarshal(c.Body(), &request); err != nil {
			log.Error().Err(err).Msg("Failed to parse request body")
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
				"error": "Invalid JSON",
			})
		}

		// Process the MCP request
		response, err := mcpServer.HandleRequest(request)
		if err != nil {
			log.Error().Err(err).Interface("request", request).Msg("Failed to handle MCP request")
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
				"error": err.Error(),
			})
		}

		return c.JSON(response)
	})

	// OAuth mock endpoints for Claude Code compatibility
	setupOAuthMockEndpoints(app)
}

func setupOAuthMockEndpoints(app *fiber.App) {
	// OAuth discovery endpoint
	app.Get("/.well-known/oauth-authorization-server", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"issuer":                   fmt.Sprintf("http://%s", c.Hostname()),
			"authorization_endpoint":   fmt.Sprintf("http://%s/authorize", c.Hostname()),
			"token_endpoint":          fmt.Sprintf("http://%s/token", c.Hostname()),
			"registration_endpoint":   fmt.Sprintf("http://%s/register", c.Hostname()),
			"response_types_supported": []string{"code"},
			"grant_types_supported":   []string{"authorization_code"},
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
			"client_id":                 clientID,
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

	log.Info().Msg("OAuth mock endpoints configured")
}