package main

import (
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
)

// Session represents an MCP session
type Session struct {
	ID           string
	CreatedAt    time.Time
	LastActivity time.Time
	Initialized  bool
	ClientInfo   *ClientInfo
	Data         map[string]interface{} // For storing session-specific data
	mu           sync.RWMutex
}

// SessionManager manages MCP sessions
type SessionManager struct {
	sessions map[string]*Session
	mu       sync.RWMutex
	ttl      time.Duration
}

// NewSessionManager creates a new session manager
func NewSessionManager(ttl time.Duration) *SessionManager {
	sm := &SessionManager{
		sessions: make(map[string]*Session),
		ttl:      ttl,
	}

	// Start cleanup goroutine if TTL is set
	if ttl > 0 {
		go sm.cleanupExpiredSessions()
	}

	return sm
}

// CreateSession creates a new session
func (sm *SessionManager) CreateSession() *Session {
	l := log.With().Str("scope", "CreateSession").Logger()

	session := &Session{
		ID:           uuid.New().String(),
		CreatedAt:    time.Now(),
		LastActivity: time.Now(),
		Data:         make(map[string]interface{}),
	}

	sm.mu.Lock()
	sm.sessions[session.ID] = session
	sm.mu.Unlock()

	l.Info().Str("session_id", session.ID).Msg("Session created")
	return session
}

// GetSession retrieves a session by ID
func (sm *SessionManager) GetSession(id string) (*Session, bool) {
	sm.mu.RLock()
	session, exists := sm.sessions[id]
	sm.mu.RUnlock()

	if exists {
		session.Touch()
	}

	return session, exists
}

// DeleteSession removes a session
func (sm *SessionManager) DeleteSession(id string) {
	l := log.With().Str("scope", "DeleteSession").Logger()

	sm.mu.Lock()
	delete(sm.sessions, id)
	sm.mu.Unlock()

	l.Info().Str("session_id", id).Msg("Session deleted")
}

// cleanupExpiredSessions periodically removes expired sessions
func (sm *SessionManager) cleanupExpiredSessions() {
	l := log.With().Str("scope", "cleanupExpiredSessions").Logger()
	ticker := time.NewTicker(sm.ttl / 2)
	defer ticker.Stop()

	for range ticker.C {
		now := time.Now()
		expired := []string{}

		sm.mu.RLock()
		for id, session := range sm.sessions {
			if now.Sub(session.LastActivity) > sm.ttl {
				expired = append(expired, id)
			}
		}
		sm.mu.RUnlock()

		// Delete expired sessions
		for _, id := range expired {
			sm.DeleteSession(id)
		}

		if len(expired) > 0 {
			l.Info().Int("count", len(expired)).Msg("Cleaned up expired sessions")
		}
	}
}

// Touch updates the last activity time
func (s *Session) Touch() {
	s.mu.Lock()
	s.LastActivity = time.Now()
	s.mu.Unlock()
}

// SetData stores data in the session
func (s *Session) SetData(key string, value interface{}) {
	s.mu.Lock()
	s.Data[key] = value
	s.mu.Unlock()
}

// GetData retrieves data from the session
func (s *Session) GetData(key string) (interface{}, bool) {
	s.mu.RLock()
	value, exists := s.Data[key]
	s.mu.RUnlock()
	return value, exists
}

// MarkInitialized marks the session as initialized
func (s *Session) MarkInitialized(clientInfo *ClientInfo) {
	s.mu.Lock()
	s.Initialized = true
	s.ClientInfo = clientInfo
	s.mu.Unlock()
}

// IsInitialized checks if the session is initialized
func (s *Session) IsInitialized() bool {
	s.mu.RLock()
	initialized := s.Initialized
	s.mu.RUnlock()
	return initialized
}
