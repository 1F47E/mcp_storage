package main

import "encoding/json"

const (
	// ProtocolVersion is the MCP protocol version this server implements
	ProtocolVersion = "2024-11-05"
)

// JSON-RPC 2.0 Types

// JSONRPCRequest represents a JSON-RPC 2.0 request
type JSONRPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

// JSONRPCResponse represents a JSON-RPC 2.0 response
type JSONRPCResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Result  interface{}     `json:"result,omitempty"`
	Error   *JSONRPCError   `json:"error,omitempty"`
}

// JSONRPCNotification represents a JSON-RPC 2.0 notification
type JSONRPCNotification struct {
	JSONRPC string          `json:"jsonrpc"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

// JSONRPCError represents a JSON-RPC 2.0 error
type JSONRPCError struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}

// Standard JSON-RPC 2.0 error codes
const (
	ParseError     = -32700
	InvalidRequest = -32600
	MethodNotFound = -32601
	InvalidParams  = -32602
	InternalError  = -32603
)

// MCP Protocol Types

// ClientInfo represents information about the client
type ClientInfo struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// ServerInfo represents information about the server
type ServerInfo struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// InitializeParams represents parameters for the initialize request
type InitializeParams struct {
	ProtocolVersion string            `json:"protocolVersion"`
	Capabilities    ClientCapabilities `json:"capabilities"`
	ClientInfo      ClientInfo        `json:"clientInfo"`
}

// InitializeResult represents the result of an initialize request
type InitializeResult struct {
	ProtocolVersion string            `json:"protocolVersion"`
	Capabilities    ServerCapabilities `json:"capabilities"`
	ServerInfo      ServerInfo        `json:"serverInfo"`
}

// ClientCapabilities represents client capabilities
type ClientCapabilities struct {
	Sampling *SamplingCapability `json:"sampling,omitempty"`
	Roots    *RootsCapability    `json:"roots,omitempty"`
}

// ServerCapabilities represents server capabilities
type ServerCapabilities struct {
	Tools     *ToolsCapability     `json:"tools,omitempty"`
	Resources *ResourcesCapability `json:"resources,omitempty"`
	Prompts   *PromptsCapability   `json:"prompts,omitempty"`
	Logging   *LoggingCapability   `json:"logging,omitempty"`
}

// Capability types
type SamplingCapability struct{}
type RootsCapability struct {
	ListChanged bool `json:"listChanged,omitempty"`
}
type ToolsCapability struct {
	ListChanged bool `json:"listChanged,omitempty"`
}
type ResourcesCapability struct {
	Subscribe   bool `json:"subscribe,omitempty"`
	ListChanged bool `json:"listChanged,omitempty"`
}
type PromptsCapability struct {
	ListChanged bool `json:"listChanged,omitempty"`
}
type LoggingCapability struct{}

// Tool represents a tool that can be called
type Tool struct {
	Name        string      `json:"name"`
	Description string      `json:"description,omitempty"`
	InputSchema InputSchema `json:"inputSchema"`
}

// InputSchema represents the JSON Schema for tool input
type InputSchema struct {
	Type       string                 `json:"type"`
	Properties map[string]interface{} `json:"properties,omitempty"`
	Required   []string               `json:"required,omitempty"`
}

// ListToolsResult represents the result of a tools/list request
type ListToolsResult struct {
	Tools []Tool `json:"tools"`
}

// CallToolParams represents parameters for a tools/call request
type CallToolParams struct {
	Name      string          `json:"name"`
	Arguments json.RawMessage `json:"arguments"`
}

// CallToolResult represents the result of a tools/call request
type CallToolResult struct {
	Content []Content `json:"content"`
	IsError bool      `json:"isError,omitempty"`
}

// Content represents content in a tool result
type Content interface {
	contentType() string
}

// TextContent represents text content
type TextContent struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

func (t TextContent) contentType() string { return "text" }

// ImageContent represents image content
type ImageContent struct {
	Type     string `json:"type"`
	Data     string `json:"data"`
	MimeType string `json:"mimeType"`
}

func (i ImageContent) contentType() string { return "image" }

// Resource represents a resource
type Resource struct {
	URI         string `json:"uri"`
	Name        string `json:"name"`
	Description string `json:"description,omitempty"`
	MimeType    string `json:"mimeType,omitempty"`
}

// Progress represents progress information
type Progress struct {
	Token      string  `json:"token"`
	Progress   float64 `json:"progress"`
	Total      float64 `json:"total,omitempty"`
	Status     string  `json:"status,omitempty"`
	StatusInfo string  `json:"statusInfo,omitempty"`
}

// LogLevel represents log levels
type LogLevel string

const (
	LogLevelDebug     LogLevel = "debug"
	LogLevelInfo      LogLevel = "info"
	LogLevelNotice    LogLevel = "notice"
	LogLevelWarning   LogLevel = "warning"
	LogLevelError     LogLevel = "error"
	LogLevelCritical  LogLevel = "critical"
	LogLevelAlert     LogLevel = "alert"
	LogLevelEmergency LogLevel = "emergency"
)

// LogEntry represents a log entry
type LogEntry struct {
	Level  LogLevel `json:"level"`
	Logger string   `json:"logger,omitempty"`
	Data   string   `json:"data"`
}