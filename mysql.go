package main

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	"github.com/rs/zerolog/log"
)

type MySQLAdapter struct {
	BaseAdapter
	url string
}

func NewMySQLAdapter(url string) *MySQLAdapter {
	return &MySQLAdapter{
		BaseAdapter: BaseAdapter{
			name:    "mysql",
			enabled: url != "",
		},
		url: url,
	}
}

func (m *MySQLAdapter) Connect() error {
	if !m.IsEnabled() {
		return nil
	}

	db, err := sql.Open("mysql", m.url)
	if err != nil {
		return fmt.Errorf("failed to open mysql connection: %w", err)
	}

	if err := db.Ping(); err != nil {
		db.Close()
		return fmt.Errorf("failed to ping mysql: %w", err)
	}

	m.db = db
	log.Info().Msg("MySQL adapter connected")
	return nil
}

func (m *MySQLAdapter) ListSchemas(ctx context.Context) ([]Schema, error) {
	query := `
		SELECT SCHEMA_NAME 
		FROM INFORMATION_SCHEMA.SCHEMATA 
		WHERE SCHEMA_NAME NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
		ORDER BY SCHEMA_NAME
	`

	rows, err := m.db.QueryContext(ctx, query)
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

func (m *MySQLAdapter) GetSchemaDDL(ctx context.Context, schemaName string) (string, error) {
	var ddls []string

	ddls = append(ddls, fmt.Sprintf("CREATE DATABASE IF NOT EXISTS `%s`;", schemaName))
	ddls = append(ddls, fmt.Sprintf("USE `%s`;", schemaName))

	tablesQuery := `
		SELECT TABLE_NAME
		FROM INFORMATION_SCHEMA.TABLES
		WHERE TABLE_SCHEMA = ?
			AND TABLE_TYPE = 'BASE TABLE'
		ORDER BY TABLE_NAME
	`

	rows, err := m.db.QueryContext(ctx, tablesQuery, schemaName)
	if err != nil {
		return "", fmt.Errorf("failed to list tables: %w", err)
	}
	defer rows.Close()

	var tables []string
	for rows.Next() {
		var tableName string
		if err := rows.Scan(&tableName); err != nil {
			return "", err
		}
		tables = append(tables, tableName)
	}

	for _, table := range tables {
		var createTable string
		showCreateQuery := fmt.Sprintf("SHOW CREATE TABLE `%s`.`%s`", schemaName, table)
		row := m.db.QueryRowContext(ctx, showCreateQuery)
		var tableName string
		if err := row.Scan(&tableName, &createTable); err != nil {
			return "", fmt.Errorf("failed to get create table statement for %s: %w", table, err)
		}
		ddls = append(ddls, createTable+";")
	}

	viewsQuery := `
		SELECT TABLE_NAME
		FROM INFORMATION_SCHEMA.VIEWS
		WHERE TABLE_SCHEMA = ?
		ORDER BY TABLE_NAME
	`

	rows, err = m.db.QueryContext(ctx, viewsQuery, schemaName)
	if err != nil {
		return "", fmt.Errorf("failed to list views: %w", err)
	}
	defer rows.Close()

	var views []string
	for rows.Next() {
		var viewName string
		if err := rows.Scan(&viewName); err != nil {
			return "", err
		}
		views = append(views, viewName)
	}

	for _, view := range views {
		var createView string
		showCreateQuery := fmt.Sprintf("SHOW CREATE VIEW `%s`.`%s`", schemaName, view)
		row := m.db.QueryRowContext(ctx, showCreateQuery)
		var viewName, characterSet, collation string
		if err := row.Scan(&viewName, &createView, &characterSet, &collation); err != nil {
			log.Warn().Err(err).Str("view", view).Msg("Failed to get create view statement")
			continue
		}
		ddls = append(ddls, createView+";")
	}

	routinesQuery := `
		SELECT ROUTINE_NAME, ROUTINE_TYPE
		FROM INFORMATION_SCHEMA.ROUTINES
		WHERE ROUTINE_SCHEMA = ?
		ORDER BY ROUTINE_NAME
	`

	rows, err = m.db.QueryContext(ctx, routinesQuery, schemaName)
	if err != nil {
		return "", fmt.Errorf("failed to list routines: %w", err)
	}
	defer rows.Close()

	type routine struct {
		name        string
		routineType string
	}
	var routines []routine

	for rows.Next() {
		var r routine
		if err := rows.Scan(&r.name, &r.routineType); err != nil {
			return "", err
		}
		routines = append(routines, r)
	}

	for _, r := range routines {
		showCreateQuery := fmt.Sprintf("SHOW CREATE %s `%s`.`%s`", r.routineType, schemaName, r.name)
		row := m.db.QueryRowContext(ctx, showCreateQuery)

		var name, sqlMode, createStatement, characterSet, collation, dbCollation string
		if err := row.Scan(&name, &sqlMode, &createStatement, &characterSet, &collation, &dbCollation); err != nil {
			log.Warn().Err(err).Str("routine", r.name).Msg("Failed to get create routine statement")
			continue
		}
		ddls = append(ddls, "DELIMITER $$")
		ddls = append(ddls, createStatement+"$$")
		ddls = append(ddls, "DELIMITER ;")
	}

	return strings.Join(ddls, "\n\n"), nil
}

func (m *MySQLAdapter) ExecuteSelect(ctx context.Context, query string) (QueryResult, error) {
	query = strings.TrimSpace(query)
	queryLower := strings.ToLower(query)

	if !strings.HasPrefix(queryLower, "select") && !strings.HasPrefix(queryLower, "with") {
		return QueryResult{}, fmt.Errorf("only SELECT queries are allowed")
	}

	rows, err := m.db.QueryContext(ctx, query)
	if err != nil {
		return QueryResult{}, fmt.Errorf("query execution failed: %w", err)
	}
	defer rows.Close()

	return scanQueryResult(rows)
}
