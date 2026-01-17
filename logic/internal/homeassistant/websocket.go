package homeassistant

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

const (
	// websocketReadDeadline is the duration for WebSocket read timeout
	websocketReadDeadline = 6 * time.Second
	// websocketPingInterval is how often we update the read deadline
	websocketPingInterval = 5 * time.Second
)

// WebSocketClient handles WebSocket connections to Home Assistant
type WebSocketClient struct {
	baseURL       string
	token         string
	conn          *websocket.Conn
	mu            sync.Mutex
	nextID        int64
	subscriptions map[int64]*Subscription
	eventHandlers map[string][]EventHandler // Changed to slice to support multiple handlers
	running       bool
	stopCh        chan struct{}
	closeOnce     sync.Once // Ensures stopCh is only closed once
}

// Subscription represents a WebSocket subscription
type Subscription struct {
	ID        int64
	EventType string
}

// EventHandler is a function that handles events
type EventHandler func(event *Event)

// Event represents a Home Assistant event
type Event struct {
	EventType string                 `json:"event_type"`
	Data      map[string]interface{} `json:"data"`
	Origin    string                 `json:"origin"`
	TimeFired string                 `json:"time_fired"`
	Context   map[string]interface{} `json:"context"`
}

// WSMessage represents a WebSocket message
type WSMessage struct {
	ID      int64                  `json:"id,omitempty"`
	Type    string                 `json:"type"`
	Event   *Event                 `json:"event,omitempty"`
	Result  interface{}            `json:"result,omitempty"`
	Success bool                   `json:"success,omitempty"`
	Error   map[string]interface{} `json:"error,omitempty"`
}

// NewWebSocketClient creates a new WebSocket client
func NewWebSocketClient(baseURL, token string) *WebSocketClient {
	return &WebSocketClient{
		baseURL:       baseURL,
		token:         token,
		subscriptions: make(map[int64]*Subscription),
		eventHandlers: make(map[string][]EventHandler),
		stopCh:        make(chan struct{}),
	}
}

// Connect establishes a WebSocket connection to Home Assistant
func (ws *WebSocketClient) Connect(ctx context.Context) error {
	ws.mu.Lock()
	defer ws.mu.Unlock()

	// Convert http:// to ws:// or https:// to wss://
	wsURL := ws.baseURL
	if len(wsURL) > 7 && wsURL[:7] == "http://" {
		wsURL = "ws://" + wsURL[7:]
	} else if len(wsURL) > 8 && wsURL[:8] == "https://" {
		wsURL = "wss://" + wsURL[8:]
	}
	wsURL += "/api/websocket"

	log.Printf("Connecting to WebSocket: %s", wsURL)

	dialer := websocket.DefaultDialer
	dialer.HandshakeTimeout = 10 * time.Second

	conn, _, err := dialer.DialContext(ctx, wsURL, http.Header{})
	if err != nil {
		return fmt.Errorf("failed to connect to websocket: %w", err)
	}

	ws.conn = conn

	// Read auth_required message
	var authRequired WSMessage
	if err := conn.ReadJSON(&authRequired); err != nil {
		conn.Close()
		return fmt.Errorf("failed to read auth_required: %w", err)
	}

	if authRequired.Type != "auth_required" {
		conn.Close()
		return fmt.Errorf("expected auth_required, got: %s", authRequired.Type)
	}

	// Send auth message
	authMsgWithToken := map[string]interface{}{
		"type":         "auth",
		"access_token": ws.token,
	}

	if err := conn.WriteJSON(authMsgWithToken); err != nil {
		conn.Close()
		return fmt.Errorf("failed to send auth: %w", err)
	}

	// Read auth result
	var authResult WSMessage
	if err := conn.ReadJSON(&authResult); err != nil {
		conn.Close()
		return fmt.Errorf("failed to read auth result: %w", err)
	}

	if authResult.Type != "auth_ok" {
		conn.Close()
		return fmt.Errorf("authentication failed: %s", authResult.Type)
	}

	log.Println("WebSocket authenticated successfully")

	ws.running = true
	ws.nextID = 1

	// Start message reader
	go ws.readMessages()

	return nil
}

// readMessages continuously reads messages from the WebSocket
func (ws *WebSocketClient) readMessages() {
	// Set read deadline to allow periodic checking of stopCh
	ticker := time.NewTicker(websocketPingInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ws.stopCh:
			return
		case <-ticker.C:
			// Update read deadline periodically
			ws.conn.SetReadDeadline(time.Now().Add(websocketReadDeadline))
		default:
			// Set read deadline for graceful shutdown
			ws.conn.SetReadDeadline(time.Now().Add(websocketReadDeadline))

			var msg WSMessage
			err := ws.conn.ReadJSON(&msg)
			if err != nil {
				// Check if it's a timeout error (normal during shutdown)
				var netErr net.Error
				if errors.As(err, &netErr) && netErr.Timeout() {
					// Check if we should stop
					select {
					case <-ws.stopCh:
						return
					default:
						continue
					}
				}
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseNormalClosure) {
					log.Printf("WebSocket read error: %v", err)
				}
				ws.mu.Lock()
				ws.running = false
				ws.mu.Unlock()
				return
			}

			// Handle event messages
			if msg.Type == "event" && msg.Event != nil {
				ws.handleEvent(msg.Event)
			}
		}
	}
}

// handleEvent processes incoming events
func (ws *WebSocketClient) handleEvent(event *Event) {
	ws.mu.Lock()
	handlers := ws.eventHandlers[event.EventType]
	ws.mu.Unlock()

	// Call all registered handlers for this event type
	for _, handler := range handlers {
		if handler != nil {
			go handler(event)
		}
	}
}

// SubscribeToStateChanges subscribes to state_changed events
func (ws *WebSocketClient) SubscribeToStateChanges(handler EventHandler) (int64, error) {
	ws.mu.Lock()
	defer ws.mu.Unlock()

	if !ws.running {
		return 0, fmt.Errorf("websocket not connected")
	}

	// Add handler to the list of handlers for this event type
	ws.eventHandlers["state_changed"] = append(ws.eventHandlers["state_changed"], handler)

	// If we're already subscribed to state_changed, return the existing subscription ID
	if ws.hasSubscription("state_changed") {
		// Find and return the existing subscription ID for this event type
		for id, sub := range ws.subscriptions {
			if sub != nil && sub.EventType == "state_changed" {
				log.Printf("Added additional handler to existing state_changed subscription (ID: %d)", id)
				return id, nil
			}
		}
	}

	// First subscription for state_changed: create a new subscription
	id := ws.nextID
	ws.nextID++

	subMsg := map[string]interface{}{
		"id":         id,
		"type":       "subscribe_events",
		"event_type": "state_changed",
	}

	if err := ws.conn.WriteJSON(subMsg); err != nil {
		// Remove the handler we just added since subscription failed
		// Note: In concurrent scenarios, this might not be the exact handler added,
		// but it's safe to remove the last one as the subscription didn't succeed
		handlers := ws.eventHandlers["state_changed"]
		if len(handlers) > 0 {
			ws.eventHandlers["state_changed"] = handlers[:len(handlers)-1]
		}
		return 0, fmt.Errorf("failed to subscribe: %w", err)
	}

	ws.subscriptions[id] = &Subscription{
		ID:        id,
		EventType: "state_changed",
	}

	log.Printf("Subscribed to state_changed events with ID: %d", id)

	return id, nil
}

// hasSubscription checks if already subscribed to an event type
func (ws *WebSocketClient) hasSubscription(eventType string) bool {
	for _, sub := range ws.subscriptions {
		if sub.EventType == eventType {
			return true
		}
	}
	return false
}

// SubscribeToEvents subscribes to specific event types
func (ws *WebSocketClient) SubscribeToEvents(eventType string, handler EventHandler) (int64, error) {
	ws.mu.Lock()
	defer ws.mu.Unlock()

	if !ws.running {
		return 0, fmt.Errorf("websocket not connected")
	}

	// Add handler to the list of handlers for this event type
	ws.eventHandlers[eventType] = append(ws.eventHandlers[eventType], handler)

	// If we're already subscribed to this event type, return the existing subscription ID
	if ws.hasSubscription(eventType) {
		// Find and return the existing subscription ID for this event type
		for id, sub := range ws.subscriptions {
			if sub != nil && sub.EventType == eventType {
				log.Printf("Added additional handler to existing %s subscription (ID: %d)", eventType, id)
				return id, nil
			}
		}
	}

	// First subscription for this event type: create a new subscription
	id := ws.nextID
	ws.nextID++

	subMsg := map[string]interface{}{
		"id":         id,
		"type":       "subscribe_events",
		"event_type": eventType,
	}

	if err := ws.conn.WriteJSON(subMsg); err != nil {
		// Remove the handler we just added since subscription failed
		handlers := ws.eventHandlers[eventType]
		if len(handlers) > 0 {
			ws.eventHandlers[eventType] = handlers[:len(handlers)-1]
		}
		return 0, fmt.Errorf("failed to subscribe: %w", err)
	}

	ws.subscriptions[id] = &Subscription{
		ID:        id,
		EventType: eventType,
	}

	log.Printf("Subscribed to %s events with ID: %d", eventType, id)

	return id, nil
}

// Unsubscribe unsubscribes from events by subscription ID
// Note: This removes the subscription but keeps event handlers as they may be used by other subscriptions
func (ws *WebSocketClient) Unsubscribe(subscriptionID int64) error {
	ws.mu.Lock()
	defer ws.mu.Unlock()

	if !ws.running {
		return fmt.Errorf("websocket not connected")
	}

	_, exists := ws.subscriptions[subscriptionID]
	if !exists {
		return fmt.Errorf("subscription not found: %d", subscriptionID)
	}

	// Send unsubscribe message
	unsubMsg := map[string]interface{}{
		"id":              ws.nextID,
		"type":            "unsubscribe_events",
		"subscription_id": subscriptionID,
	}
	ws.nextID++

	if err := ws.conn.WriteJSON(unsubMsg); err != nil {
		return fmt.Errorf("failed to unsubscribe: %w", err)
	}

	delete(ws.subscriptions, subscriptionID)
	// Note: We don't delete event handlers as other subscriptions may still use them

	log.Printf("Unsubscribed from subscription ID: %d", subscriptionID)

	return nil
}

// Close closes the WebSocket connection
func (ws *WebSocketClient) Close() error {
	ws.mu.Lock()
	defer ws.mu.Unlock()

	if !ws.running {
		return nil
	}

	// Set running to false first to prevent race condition
	ws.running = false

	// Use sync.Once to ensure stopCh is only closed once
	ws.closeOnce.Do(func() {
		close(ws.stopCh)
	})

	if ws.conn != nil {
		return ws.conn.Close()
	}

	return nil
}

// IsConnected returns whether the WebSocket is connected
func (ws *WebSocketClient) IsConnected() bool {
	ws.mu.Lock()
	defer ws.mu.Unlock()
	return ws.running
}
