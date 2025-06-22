package main

import (
	"encoding/json"
	"fmt"
	"sync"

	"github.com/rs/zerolog/log"
)

// JSONRPCHandler handles JSON-RPC requests
type JSONRPCHandler struct {
	methods map[string]MethodHandler
	mu      sync.RWMutex
}

// MethodHandler is a function that handles a JSON-RPC method
type MethodHandler func(params json.RawMessage) (interface{}, error)

// NewJSONRPCHandler creates a new JSON-RPC handler
func NewJSONRPCHandler() *JSONRPCHandler {
	return &JSONRPCHandler{
		methods: make(map[string]MethodHandler),
	}
}

// RegisterMethod registers a method handler
func (h *JSONRPCHandler) RegisterMethod(method string, handler MethodHandler) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.methods[method] = handler
}

// HandleRequest processes a JSON-RPC request and returns a response
func (h *JSONRPCHandler) HandleRequest(data []byte) []byte {
	l := log.With().Str("scope", "HandleRequest").Logger()
	
	// Try to parse as single request first
	var req JSONRPCRequest
	if err := json.Unmarshal(data, &req); err == nil {
		if debugMode {
			l.Debug().RawJSON("request", data).Msg("Handling single request")
		}
		return h.handleSingleRequest(&req)
	}

	// Try to parse as batch request
	var batch []JSONRPCRequest
	if err := json.Unmarshal(data, &batch); err == nil {
		if debugMode {
			l.Debug().RawJSON("request", data).Msg("Handling batch request")
		}
		return h.handleBatchRequest(batch)
	}

	// Invalid JSON
	return h.createErrorResponse(nil, ParseError, "Parse error", nil)
}

// handleSingleRequest processes a single JSON-RPC request
func (h *JSONRPCHandler) handleSingleRequest(req *JSONRPCRequest) []byte {
	l := log.With().Str("scope", "handleSingleRequest").Str("method", req.Method).Logger()

	// Validate JSON-RPC version
	if req.JSONRPC != "2.0" {
		return h.createErrorResponse(req.ID, InvalidRequest, "Invalid Request", "JSON-RPC version must be 2.0")
	}

	// Check if it's a notification (no ID)
	isNotification := req.ID == nil

	// Find method handler
	h.mu.RLock()
	handler, exists := h.methods[req.Method]
	h.mu.RUnlock()

	if !exists {
		if isNotification {
			// Notifications don't get error responses
			return nil
		}
		return h.createErrorResponse(req.ID, MethodNotFound, "Method not found", nil)
	}

	// Execute method
	result, err := handler(req.Params)
	if err != nil {
		if isNotification {
			l.Error().Err(err).Msg("Error in notification handler")
			return nil
		}
		
		// Check if error is a JSONRPCError
		if rpcErr, ok := err.(*JSONRPCError); ok {
			return h.createErrorResponse(req.ID, rpcErr.Code, rpcErr.Message, rpcErr.Data)
		}
		
		// Generic error
		return h.createErrorResponse(req.ID, InternalError, "Internal error", err.Error())
	}

	// Don't send response for notifications
	if isNotification {
		return nil
	}

	// Create success response
	resp := JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result:  result,
	}

	respData, _ := json.Marshal(resp)
	if debugMode {
		l.Debug().RawJSON("response", respData).Msg("Sending response")
	}
	return respData
}

// handleBatchRequest processes a batch of JSON-RPC requests
func (h *JSONRPCHandler) handleBatchRequest(batch []JSONRPCRequest) []byte {
	if len(batch) == 0 {
		return h.createErrorResponse(nil, InvalidRequest, "Invalid Request", "Batch cannot be empty")
	}

	var responses []json.RawMessage
	for _, req := range batch {
		if resp := h.handleSingleRequest(&req); resp != nil {
			responses = append(responses, resp)
		}
	}

	// If no responses (all notifications), return nothing
	if len(responses) == 0 {
		return nil
	}

	// Combine responses
	result, _ := json.Marshal(responses)
	return result
}

// createErrorResponse creates a JSON-RPC error response
func (h *JSONRPCHandler) createErrorResponse(id json.RawMessage, code int, message string, data interface{}) []byte {
	resp := JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error: &JSONRPCError{
			Code:    code,
			Message: message,
			Data:    data,
		},
	}
	
	result, _ := json.Marshal(resp)
	return result
}

// NewRPCError creates a new JSON-RPC error
func NewRPCError(code int, message string, data interface{}) error {
	return &JSONRPCError{
		Code:    code,
		Message: message,
		Data:    data,
	}
}

// Error implements the error interface for JSONRPCError
func (e *JSONRPCError) Error() string {
	return fmt.Sprintf("JSON-RPC error %d: %s", e.Code, e.Message)
}