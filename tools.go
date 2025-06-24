package main

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"

	"github.com/rs/zerolog/log"
)

// ToolRegistry manages available tools
type ToolRegistry struct {
	tools    map[string]Tool
	handlers map[string]ToolHandler
	mu       sync.RWMutex
}

// ToolHandler is a function that handles tool execution
type ToolHandler func(ctx context.Context, arguments json.RawMessage) (*CallToolResult, error)

// NewToolRegistry creates a new tool registry
func NewToolRegistry() *ToolRegistry {
	return &ToolRegistry{
		tools:    make(map[string]Tool),
		handlers: make(map[string]ToolHandler),
	}
}

// RegisterTool registers a tool with its handler
func (r *ToolRegistry) RegisterTool(tool Tool, handler ToolHandler) {
	l := log.With().Str("scope", "RegisterTool").Logger()

	r.mu.Lock()
	defer r.mu.Unlock()

	r.tools[tool.Name] = tool
	r.handlers[tool.Name] = handler

	l.Debug().Str("tool", tool.Name).Msg("Tool registered")
}

// ListTools returns all registered tools
func (r *ToolRegistry) ListTools() []Tool {
	r.mu.RLock()
	defer r.mu.RUnlock()

	tools := make([]Tool, 0, len(r.tools))
	for _, tool := range r.tools {
		tools = append(tools, tool)
	}
	return tools
}

// CallTool executes a tool by name
func (r *ToolRegistry) CallTool(ctx context.Context, name string, arguments json.RawMessage) (*CallToolResult, error) {
	l := log.With().Str("scope", "CallTool").Str("tool", name).Logger()

	r.mu.RLock()
	handler, exists := r.handlers[name]
	r.mu.RUnlock()

	if !exists {
		l.Error().Msg("Tool not found")
		return nil, fmt.Errorf("tool not found: %s", name)
	}

	if debugMode {
		l.Debug().RawJSON("arguments", arguments).Msg("Calling tool")
	}

	result, err := handler(ctx, arguments)
	if err != nil {
		l.Error().Err(err).Msg("Tool execution failed")
		return nil, err
	}

	if debugMode {
		l.Debug().Interface("result", result).Msg("Tool execution completed")
	}

	return result, nil
}

// RegisterTools registers all tools for the MCP server
func RegisterTools(registry *ToolRegistry, adapters *AdapterRegistry) {
	l := log.With().Str("scope", "RegisterTools").Logger()


	// PostgreSQL tools
	if adapter, ok := adapters.Get("postgres"); ok {
		postgresAdapter := adapter.(*PostgresAdapter)

		// postgres_schemas tool
		registry.RegisterTool(
			Tool{
				Name:        "postgres_schemas",
				Description: "List all schemas in the PostgreSQL database",
				InputSchema: InputSchema{
					Type:       "object",
					Properties: map[string]interface{}{},
				},
			},
			func(ctx context.Context, arguments json.RawMessage) (*CallToolResult, error) {
				schemas, err := postgresAdapter.ListSchemas(ctx)
				if err != nil {
					return nil, err
				}

				// Convert to JSON
				schemasJSON, err := json.Marshal(map[string]interface{}{"schemas": schemas})
				if err != nil {
					return nil, err
				}

				return &CallToolResult{
					Content: []Content{
						TextContent{
							Type: "text",
							Text: string(schemasJSON),
						},
					},
				}, nil
			},
		)

		// postgres_schema_ddls tool
		registry.RegisterTool(
			Tool{
				Name:        "postgres_schema_ddls",
				Description: "Get DDL statements for a PostgreSQL schema",
				InputSchema: InputSchema{
					Type: "object",
					Properties: map[string]interface{}{
						"schema_name": map[string]interface{}{
							"type":        "string",
							"description": "Name of the schema",
						},
					},
					Required: []string{"schema_name"},
				},
			},
			func(ctx context.Context, arguments json.RawMessage) (*CallToolResult, error) {
				var params struct {
					SchemaName string `json:"schema_name"`
				}

				if err := json.Unmarshal(arguments, &params); err != nil {
					return nil, fmt.Errorf("invalid parameters: %w", err)
				}

				if params.SchemaName == "" {
					return nil, fmt.Errorf("schema_name is required")
				}

				ddl, err := postgresAdapter.GetSchemaDDL(ctx, params.SchemaName)
				if err != nil {
					return nil, err
				}

				return &CallToolResult{
					Content: []Content{
						TextContent{
							Type: "text",
							Text: ddl,
						},
					},
				}, nil
			},
		)

		// postgres_query_select tool
		registry.RegisterTool(
			Tool{
				Name:        "postgres_query_select",
				Description: "Execute a SELECT query on PostgreSQL database",
				InputSchema: InputSchema{
					Type: "object",
					Properties: map[string]interface{}{
						"query": map[string]interface{}{
							"type":        "string",
							"description": "SELECT query to execute",
						},
					},
					Required: []string{"query"},
				},
			},
			func(ctx context.Context, arguments json.RawMessage) (*CallToolResult, error) {
				var params struct {
					Query string `json:"query"`
				}

				if err := json.Unmarshal(arguments, &params); err != nil {
					return nil, fmt.Errorf("invalid parameters: %w", err)
				}

				if params.Query == "" {
					return nil, fmt.Errorf("query is required")
				}

				result, err := postgresAdapter.ExecuteSelect(ctx, params.Query)
				if err != nil {
					return nil, err
				}

				// Convert to JSON
				resultJSON, err := json.Marshal(result)
				if err != nil {
					return nil, err
				}

				return &CallToolResult{
					Content: []Content{
						TextContent{
							Type: "text",
							Text: string(resultJSON),
						},
					},
				}, nil
			},
		)
	}

	// MySQL tools
	if adapter, ok := adapters.Get("mysql"); ok {
		mysqlAdapter := adapter.(*MySQLAdapter)

		// mysql_query_select tool
		registry.RegisterTool(
			Tool{
				Name:        "mysql_query_select",
				Description: "Execute a SELECT query on MySQL database",
				InputSchema: InputSchema{
					Type: "object",
					Properties: map[string]interface{}{
						"query": map[string]interface{}{
							"type":        "string",
							"description": "SELECT query to execute",
						},
					},
					Required: []string{"query"},
				},
			},
			func(ctx context.Context, arguments json.RawMessage) (*CallToolResult, error) {
				var params struct {
					Query string `json:"query"`
				}

				if err := json.Unmarshal(arguments, &params); err != nil {
					return nil, fmt.Errorf("invalid parameters: %w", err)
				}

				if params.Query == "" {
					return nil, fmt.Errorf("query is required")
				}

				result, err := mysqlAdapter.ExecuteSelect(ctx, params.Query)
				if err != nil {
					return nil, err
				}

				// Convert to JSON
				resultJSON, err := json.Marshal(result)
				if err != nil {
					return nil, err
				}

				return &CallToolResult{
					Content: []Content{
						TextContent{
							Type: "text",
							Text: string(resultJSON),
						},
					},
				}, nil
			},
		)

		// mysql_schema_ddls tool
		registry.RegisterTool(
			Tool{
				Name:        "mysql_schema_ddls",
				Description: "Get DDL statements for a MySQL schema",
				InputSchema: InputSchema{
					Type: "object",
					Properties: map[string]interface{}{
						"schema_name": map[string]interface{}{
							"type":        "string",
							"description": "Name of the schema",
						},
					},
					Required: []string{"schema_name"},
				},
			},
			func(ctx context.Context, arguments json.RawMessage) (*CallToolResult, error) {
				var params struct {
					SchemaName string `json:"schema_name"`
				}

				if err := json.Unmarshal(arguments, &params); err != nil {
					return nil, fmt.Errorf("invalid parameters: %w", err)
				}

				if params.SchemaName == "" {
					return nil, fmt.Errorf("schema_name is required")
				}

				ddl, err := mysqlAdapter.GetSchemaDDL(ctx, params.SchemaName)
				if err != nil {
					return nil, err
				}

				return &CallToolResult{
					Content: []Content{
						TextContent{
							Type: "text",
							Text: ddl,
						},
					},
				}, nil
			},
		)
	}

	l.Info().Int("total_tools", len(registry.ListTools())).Msg("Tools registered")
}
