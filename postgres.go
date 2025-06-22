package main

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	_ "github.com/lib/pq"
	"github.com/rs/zerolog/log"
)

type PostgresAdapter struct {
	BaseAdapter
	connectionString string
}

func NewPostgresAdapter(connectionString string) *PostgresAdapter {
	return &PostgresAdapter{
		BaseAdapter: BaseAdapter{
			name:    "postgres",
			enabled: connectionString != "",
		},
		connectionString: connectionString,
	}
}

func (p *PostgresAdapter) Connect() error {
	if !p.IsEnabled() {
		return nil
	}

	db, err := sql.Open("postgres", p.connectionString)
	if err != nil {
		return fmt.Errorf("failed to open postgres connection: %w", err)
	}

	if err := db.Ping(); err != nil {
		db.Close()
		return fmt.Errorf("failed to ping postgres: %w", err)
	}

	p.db = db
	log.Info().Msg("PostgreSQL adapter connected")
	return nil
}

func (p *PostgresAdapter) ListSchemas(ctx context.Context) ([]Schema, error) {
	query := `
		SELECT schema_name 
		FROM information_schema.schemata 
		WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
		ORDER BY schema_name
	`

	rows, err := p.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to list schemas: %w", err)
	}
	defer rows.Close()

	var schemas []Schema
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, fmt.Errorf("failed to scan schema: %w", err)
		}
		schemas = append(schemas, Schema{Name: name})
	}

	return schemas, rows.Err()
}

func (p *PostgresAdapter) GetSchemaDDL(ctx context.Context, schemaName string) (string, error) {
	var ddls []string

	schemaQuery := fmt.Sprintf(`
		SELECT 'CREATE SCHEMA IF NOT EXISTS %s;' as ddl
	`, schemaName)

	rows, err := p.db.QueryContext(ctx, schemaQuery)
	if err != nil {
		return "", fmt.Errorf("failed to get schema DDL: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var ddl string
		if err := rows.Scan(&ddl); err != nil {
			return "", err
		}
		ddls = append(ddls, ddl)
	}

	tablesQuery := `
		SELECT 
			'CREATE TABLE ' || schemaname || '.' || tablename || ' (' || 
			string_agg(
				attname || ' ' || 
				format_type(atttypid, atttypmod) || 
				CASE WHEN attnotnull THEN ' NOT NULL' ELSE '' END,
				', ' ORDER BY attnum
			) || ');' as ddl
		FROM pg_attribute a
		JOIN pg_class c ON a.attrelid = c.oid
		JOIN pg_namespace n ON c.relnamespace = n.oid
		JOIN pg_tables t ON c.relname = t.tablename AND n.nspname = t.schemaname
		WHERE a.attnum > 0 
			AND NOT a.attisdropped
			AND n.nspname = $1
		GROUP BY schemaname, tablename
		ORDER BY tablename
	`

	rows, err = p.db.QueryContext(ctx, tablesQuery, schemaName)
	if err != nil {
		return "", fmt.Errorf("failed to get table DDLs: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var ddl string
		if err := rows.Scan(&ddl); err != nil {
			return "", err
		}
		ddls = append(ddls, ddl)
	}

	indexQuery := `
		SELECT 
			pg_get_indexdef(i.indexrelid) || ';' as ddl
		FROM pg_index i
		JOIN pg_class c ON i.indrelid = c.oid
		JOIN pg_namespace n ON c.relnamespace = n.oid
		WHERE n.nspname = $1
			AND NOT i.indisprimary
		ORDER BY c.relname, i.indexrelid
	`

	rows, err = p.db.QueryContext(ctx, indexQuery, schemaName)
	if err != nil {
		return "", fmt.Errorf("failed to get index DDLs: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var ddl string
		if err := rows.Scan(&ddl); err != nil {
			return "", err
		}
		ddls = append(ddls, ddl)
	}

	constraintQuery := `
		SELECT 
			'ALTER TABLE ' || n.nspname || '.' || c.relname || 
			' ADD CONSTRAINT ' || con.conname || ' ' ||
			pg_get_constraintdef(con.oid) || ';' as ddl
		FROM pg_constraint con
		JOIN pg_class c ON con.conrelid = c.oid
		JOIN pg_namespace n ON c.relnamespace = n.oid
		WHERE n.nspname = $1
			AND con.contype IN ('f', 'u', 'c')
		ORDER BY c.relname, con.conname
	`

	rows, err = p.db.QueryContext(ctx, constraintQuery, schemaName)
	if err != nil {
		return "", fmt.Errorf("failed to get constraint DDLs: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var ddl string
		if err := rows.Scan(&ddl); err != nil {
			return "", err
		}
		ddls = append(ddls, ddl)
	}

	return strings.Join(ddls, "\n\n"), nil
}

func (p *PostgresAdapter) ExecuteSelect(ctx context.Context, query string) (QueryResult, error) {
	query = strings.TrimSpace(query)
	queryLower := strings.ToLower(query)

	if !strings.HasPrefix(queryLower, "select") && !strings.HasPrefix(queryLower, "with") {
		return QueryResult{}, fmt.Errorf("only SELECT queries are allowed")
	}

	rows, err := p.db.QueryContext(ctx, query)
	if err != nil {
		return QueryResult{}, fmt.Errorf("query execution failed: %w", err)
	}
	defer rows.Close()

	return scanQueryResult(rows)
}
