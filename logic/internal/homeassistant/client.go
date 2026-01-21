package homeassistant

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
)

// Entity represents a Home Assistant entity
type Entity struct {
	EntityID     string                 `json:"entity_id"`
	State        string                 `json:"state"`
	Attributes   map[string]interface{} `json:"attributes"`
	LastChanged  string                 `json:"last_changed"`
	LastUpdated  string                 `json:"last_updated"`
	FriendlyName string                 `json:"friendly_name,omitempty"`
}

// Client represents a Home Assistant API client
type Client struct {
	baseURL    string
	token      string
	httpClient *http.Client
}

// NewClientFromEnv creates a new Home Assistant API client from environment
// This works both in standalone mode and in addon mode (using Supervisor)
func NewClientFromEnv() *Client {
	// Try Supervisor token first (for addon mode)
	supervisorToken := os.Getenv("SUPERVISOR_TOKEN")
	if supervisorToken != "" {
		logger.Info("Using Supervisor token for Home Assistant API access")
		return &Client{
			baseURL: "http://supervisor/core",
			token:   supervisorToken,
			httpClient: &http.Client{
				Timeout: 10 * time.Second,
			},
		}
	}

	// Fall back to manual configuration (for standalone mode)
	haToken := os.Getenv("HA_TOKEN")
	haBaseURL := os.Getenv("HA_BASE_URL")
	
	if haToken == "" || haBaseURL == "" {
		logger.Warn("Home Assistant integration not configured (no SUPERVISOR_TOKEN or HA_TOKEN)")
		return nil
	}

	logger.Info("Using manual HA configuration for API access")
	return &Client{
		baseURL: strings.TrimRight(haBaseURL, "/"),
		token:   haToken,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// GetStates retrieves all states from Home Assistant
func (c *Client) GetStates() ([]Entity, error) {
	if c == nil {
		return nil, fmt.Errorf("home assistant client not initialized")
	}

	url := fmt.Sprintf("%s/api/states", c.baseURL)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, string(body))
	}

	var entities []Entity
	if err := json.NewDecoder(resp.Body).Decode(&entities); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	// Populate friendly_name from attributes if available
	for i := range entities {
		if friendlyName, ok := entities[i].Attributes["friendly_name"].(string); ok {
			entities[i].FriendlyName = friendlyName
		}
	}

	return entities, nil
}

// GetEntitiesByDomains retrieves entities filtered by domains
func (c *Client) GetEntitiesByDomains(domains []string) ([]Entity, error) {
	if c == nil {
		// If HA client is not configured, return empty list
		logger.Debug("Home Assistant client not initialized, returning empty entity list")
		return []Entity{}, nil
	}

	allEntities, err := c.GetStates()
	if err != nil {
		return nil, err
	}

	if len(domains) == 0 {
		return allEntities, nil
	}

	// Create a map for faster domain lookup
	domainMap := make(map[string]bool)
	for _, domain := range domains {
		domainMap[strings.ToLower(strings.TrimSpace(domain))] = true
	}

	// Filter entities by domain
	var filtered []Entity
	for _, entity := range allEntities {
		parts := strings.SplitN(entity.EntityID, ".", 2)
		if len(parts) == 2 {
			entityDomain := strings.ToLower(parts[0])
			if domainMap[entityDomain] {
				filtered = append(filtered, entity)
			}
		}
	}

	return filtered, nil
}
