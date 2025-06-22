package main

import (
	"context"
	"database/sql"
	"fmt"
	"sync"

	"github.com/rs/zerolog/log"
)

type Schema struct {
	Name string `json:"name"`
}

type QueryResult struct {
	Columns []string        `json:"columns"`
	Rows    [][]interface{} `json:"rows"`
}

type DatabaseAdapter interface {
	Name() string
	Connect() error
	Close() error
	IsEnabled() bool

	ListSchemas(ctx context.Context) ([]Schema, error)
	GetSchemaDDL(ctx context.Context, schemaName string) (string, error)
	ExecuteSelect(ctx context.Context, query string) (QueryResult, error)
}

type AdapterRegistry struct {
	mu       sync.RWMutex
	adapters map[string]DatabaseAdapter
}

func NewAdapterRegistry() *AdapterRegistry {
	return &AdapterRegistry{
		adapters: make(map[string]DatabaseAdapter),
	}
}

func (r *AdapterRegistry) Register(adapter DatabaseAdapter) error {
	if !adapter.IsEnabled() {
		return nil
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	name := adapter.Name()
	if _, exists := r.adapters[name]; exists {
		return fmt.Errorf("adapter %s already registered", name)
	}

	if err := adapter.Connect(); err != nil {
		return fmt.Errorf("failed to connect adapter %s: %w", name, err)
	}

	r.adapters[name] = adapter
	log.Info().Str("adapter", name).Msg("Database adapter registered")
	return nil
}

func (r *AdapterRegistry) Get(name string) (DatabaseAdapter, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	adapter, ok := r.adapters[name]
	return adapter, ok
}

func (r *AdapterRegistry) List() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	names := make([]string, 0, len(r.adapters))
	for name := range r.adapters {
		names = append(names, name)
	}
	return names
}

func (r *AdapterRegistry) Close() error {
	r.mu.Lock()
	defer r.mu.Unlock()

	var errors []error
	for name, adapter := range r.adapters {
		if err := adapter.Close(); err != nil {
			errors = append(errors, fmt.Errorf("failed to close adapter %s: %w", name, err))
		}
	}

	if len(errors) > 0 {
		return fmt.Errorf("failed to close adapters: %v", errors)
	}
	return nil
}

func (r *AdapterRegistry) IsEmpty() bool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.adapters) == 0
}

type BaseAdapter struct {
	db      *sql.DB
	enabled bool
	name    string
}

func (b *BaseAdapter) Name() string {
	return b.name
}

func (b *BaseAdapter) IsEnabled() bool {
	return b.enabled
}

func (b *BaseAdapter) Close() error {
	if b.db != nil {
		return b.db.Close()
	}
	return nil
}

func scanQueryResult(rows *sql.Rows) (QueryResult, error) {
	columns, err := rows.Columns()
	if err != nil {
		return QueryResult{}, err
	}

	var result QueryResult
	result.Columns = columns

	for rows.Next() {
		values := make([]interface{}, len(columns))
		valuePtrs := make([]interface{}, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}

		if err := rows.Scan(valuePtrs...); err != nil {
			return QueryResult{}, err
		}

		row := make([]interface{}, len(columns))
		for i, v := range values {
			switch val := v.(type) {
			case []byte:
				row[i] = string(val)
			case nil:
				row[i] = nil
			default:
				row[i] = val
			}
		}
		result.Rows = append(result.Rows, row)
	}

	if err := rows.Err(); err != nil {
		return QueryResult{}, err
	}

	return result, nil
}
