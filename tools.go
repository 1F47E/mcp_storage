package main

import (
	"context"
	"crypto/rand"
	"encoding/binary"
	"encoding/json"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
	"github.com/rs/zerolog/log"
)

func registerTools(s *server.MCPServer, registry *AdapterRegistry) {
	// Always available tool
	tool := mcp.NewTool("random_uint64",
		mcp.WithDescription("Generate a random 64-bit unsigned integer"),
		mcp.WithEmptyInputSchema(),
	)
	s.AddTool(tool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		var n uint64
		if err := binary.Read(rand.Reader, binary.BigEndian, &n); err != nil {
			return nil, fmt.Errorf("failed to generate random number: %w", err)
		}
		return &mcp.CallToolResult{
			Content: []interface{}{
				mcp.TextContent{
					Type: "text",
					Text: fmt.Sprintf(`{"value": %d}`, n),
				},
			},
		}, nil
	})

	// PostgreSQL tools
	if adapter, ok := registry.Get("postgres"); ok {
		postgresAdapter := adapter.(*PostgresAdapter)

		// List schemas tool
		tool := mcp.NewTool("postgres_schemas",
			mcp.WithDescription("List all schemas in the PostgreSQL database"),
			mcp.WithEmptyInputSchema(),
		)
		s.AddTool(tool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			schemas, err := postgresAdapter.ListSchemas(ctx)
			if err != nil {
				return nil, err
			}
			
			schemasJSON, err := json.Marshal(map[string]interface{}{"schemas": schemas})
			if err != nil {
				return nil, err
			}
			
			return &mcp.CallToolResult{
				Content: []interface{}{
					mcp.TextContent{
						Type: "text",
						Text: string(schemasJSON),
					},
				},
			}, nil
		})

		// Get schema DDL tool
		schemaDDLTool := mcp.NewTool("postgres_schema_ddls",
			mcp.WithDescription("Get DDL statements for a PostgreSQL schema"),
			mcp.WithObjectInputSchema(mcp.ObjectSchema{
				Properties: map[string]mcp.PropertySchema{
					"schema_name": {
						Type:        mcp.PropertyTypeString,
						Description: "Name of the schema",
					},
				},
				Required: []string{"schema_name"},
			}),
		)
		s.AddTool(schemaDDLTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			var params struct {
				SchemaName string `json:"schema_name"`
			}
			
			if err := json.Unmarshal([]byte(request.Params), &params); err != nil {
				return nil, fmt.Errorf("invalid parameters: %w", err)
			}
			
			if params.SchemaName == "" {
				return nil, fmt.Errorf("schema_name is required")
			}

			ddl, err := postgresAdapter.GetSchemaDDL(ctx, params.SchemaName)
			if err != nil {
				return nil, err
			}

			return &mcp.CallToolResult{
				Content: []interface{}{
					mcp.TextContent{
						Type: "text",
						Text: ddl,
					},
				},
			}, nil
		})

		// Execute SELECT query tool
		queryTool := mcp.NewTool("postgres_query_select",
			mcp.WithDescription("Execute a SELECT query on PostgreSQL database"),
			mcp.WithObjectInputSchema(mcp.ObjectSchema{
				Properties: map[string]mcp.PropertySchema{
					"query": {
						Type:        mcp.PropertyTypeString,
						Description: "SELECT query to execute",
					},
				},
				Required: []string{"query"},
			}),
		)
		s.AddTool(queryTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			var params struct {
				Query string `json:"query"`
			}
			
			if err := json.Unmarshal([]byte(request.Params), &params); err != nil {
				return nil, fmt.Errorf("invalid parameters: %w", err)
			}
			
			if params.Query == "" {
				return nil, fmt.Errorf("query is required")
			}

			result, err := postgresAdapter.ExecuteSelect(ctx, params.Query)
			if err != nil {
				return nil, err
			}

			resultJSON, err := json.Marshal(result)
			if err != nil {
				return nil, err
			}

			return &mcp.CallToolResult{
				Content: []interface{}{
					mcp.TextContent{
						Type: "text",
						Text: string(resultJSON),
					},
				},
			}, nil
		})
	}

	// MySQL tools
	if adapter, ok := registry.Get("mysql"); ok {
		mysqlAdapter := adapter.(*MySQLAdapter)

		// Execute SELECT query tool
		queryTool := mcp.NewTool("mysql_query_select",
			mcp.WithDescription("Execute a SELECT query on MySQL database"),
			mcp.WithObjectInputSchema(mcp.ObjectSchema{
				Properties: map[string]mcp.PropertySchema{
					"query": {
						Type:        mcp.PropertyTypeString,
						Description: "SELECT query to execute",
					},
				},
				Required: []string{"query"},
			}),
		)
		s.AddTool(queryTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			var params struct {
				Query string `json:"query"`
			}
			
			if err := json.Unmarshal([]byte(request.Params), &params); err != nil {
				return nil, fmt.Errorf("invalid parameters: %w", err)
			}
			
			if params.Query == "" {
				return nil, fmt.Errorf("query is required")
			}

			result, err := mysqlAdapter.ExecuteSelect(ctx, params.Query)
			if err != nil {
				return nil, err
			}

			resultJSON, err := json.Marshal(result)
			if err != nil {
				return nil, err
			}

			return &mcp.CallToolResult{
				Content: []interface{}{
					mcp.TextContent{
						Type: "text",
						Text: string(resultJSON),
					},
				},
			}, nil
		})

		// Get schema DDL tool
		schemaDDLTool := mcp.NewTool("mysql_schema_ddls",
			mcp.WithDescription("Get DDL statements for a MySQL schema"),
			mcp.WithObjectInputSchema(mcp.ObjectSchema{
				Properties: map[string]mcp.PropertySchema{
					"schema_name": {
						Type:        mcp.PropertyTypeString,
						Description: "Name of the schema",
					},
				},
				Required: []string{"schema_name"},
			}),
		)
		s.AddTool(schemaDDLTool, func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			var params struct {
				SchemaName string `json:"schema_name"`
			}
			
			if err := json.Unmarshal([]byte(request.Params), &params); err != nil {
				return nil, fmt.Errorf("invalid parameters: %w", err)
			}
			
			if params.SchemaName == "" {
				return nil, fmt.Errorf("schema_name is required")
			}

			ddl, err := mysqlAdapter.GetSchemaDDL(ctx, params.SchemaName)
			if err != nil {
				return nil, err
			}

			return &mcp.CallToolResult{
				Content: []interface{}{
					mcp.TextContent{
						Type: "text",
						Text: ddl,
					},
				},
			}, nil
		})
	}

	tools := s.ListTools()
	log.Info().
		Int("total_tools", len(tools)).
		Msg("Tools registered")
}