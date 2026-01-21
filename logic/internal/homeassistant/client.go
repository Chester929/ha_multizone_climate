package homeassistant

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
	
	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
)

// retryWithBackoff retries a function with exponential backoff
func retryWithBackoff(ctx context.Context, maxRetries int, initialDelay time.Duration, operation func() error) error {
	var lastErr error
	delay := initialDelay

	for attempt := 0; attempt < maxRetries; attempt++ {
		if err := operation(); err == nil {
			return nil
		} else {
			lastErr = err
			if attempt < maxRetries-1 {
				logger.Debug("Retry attempt %d/%d failed: %v, retrying in %v", attempt+1, maxRetries, err, delay)
				select {
				case <-time.After(delay):
					// Continue to next attempt
					delay *= 2 // Exponential backoff
				case <-ctx.Done():
					return fmt.Errorf("context cancelled during retry: %w", ctx.Err())
				}
			}
		}
	}

	return fmt.Errorf("operation failed after %d attempts: %w", maxRetries, lastErr)
}

// Client represents a Home Assistant API client
type Client struct {
	baseURL    string
	token      string
	httpClient *http.Client
}

// NewClient creates a new Home Assistant API client
func NewClient(baseURL, token string) *Client {
	return &Client{
		baseURL: baseURL,
		token:   token,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// EntityState represents the state of a Home Assistant entity
type EntityState struct {
	EntityID    string                 `json:"entity_id"`
	State       string                 `json:"state"`
	Attributes  map[string]interface{} `json:"attributes"`
	LastChanged string                 `json:"last_changed"`
	LastUpdated string                 `json:"last_updated"`
}

// ServiceCall represents a service call request
type ServiceCall struct {
	Domain  string                 `json:"-"`
	Service string                 `json:"-"`
	Data    map[string]interface{} `json:"service_data,omitempty"`
	Target  *ServiceTarget         `json:"target,omitempty"`
}

// ServiceTarget represents the target of a service call
type ServiceTarget struct {
	EntityID  string   `json:"entity_id,omitempty"`
	EntityIDs []string `json:"entity_ids,omitempty"`
}

// GetState retrieves the state of a single entity
func (c *Client) GetState(ctx context.Context, entityID string) (*EntityState, error) {
	url := fmt.Sprintf("%s/api/states/%s", c.baseURL, entityID)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to get state: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status code: %d, body: %s", resp.StatusCode, string(body))
	}

	var state EntityState
	if err := json.NewDecoder(resp.Body).Decode(&state); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &state, nil
}

// GetStates retrieves all entity states
func (c *Client) GetStates(ctx context.Context) ([]EntityState, error) {
	url := fmt.Sprintf("%s/api/states", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to get states: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status code: %d, body: %s", resp.StatusCode, string(body))
	}

	var states []EntityState
	if err := json.NewDecoder(resp.Body).Decode(&states); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return states, nil
}

// CallService calls a Home Assistant service with retry logic
func (c *Client) CallService(ctx context.Context, call *ServiceCall) error {
	return retryWithBackoff(ctx, 3, 500*time.Millisecond, func() error {
		url := fmt.Sprintf("%s/api/services/%s/%s", c.baseURL, call.Domain, call.Service)

		// Prepare request body
		requestBody := make(map[string]interface{})
		if call.Data != nil {
			requestBody["service_data"] = call.Data
		}
		if call.Target != nil {
			requestBody["target"] = call.Target
		}

		jsonBody, err := json.Marshal(requestBody)
		if err != nil {
			return fmt.Errorf("failed to marshal request: %w", err)
		}

		req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(jsonBody))
		if err != nil {
			return fmt.Errorf("failed to create request: %w", err)
		}

		req.Header.Set("Authorization", "Bearer "+c.token)
		req.Header.Set("Content-Type", "application/json")

		resp, err := c.httpClient.Do(req)
		if err != nil {
			return fmt.Errorf("failed to call service: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
			body, _ := io.ReadAll(resp.Body)
			return fmt.Errorf("unexpected status code: %d, body: %s", resp.StatusCode, string(body))
		}

		logger.Debug("Service call successful: %s.%s", call.Domain, call.Service)
		return nil
	})
}

// TurnOnSwitch turns on a switch entity
func (c *Client) TurnOnSwitch(ctx context.Context, entityID string) error {
	return c.CallService(ctx, &ServiceCall{
		Domain:  "switch",
		Service: "turn_on",
		Target: &ServiceTarget{
			EntityID: entityID,
		},
	})
}

// TurnOffSwitch turns off a switch entity
func (c *Client) TurnOffSwitch(ctx context.Context, entityID string) error {
	return c.CallService(ctx, &ServiceCall{
		Domain:  "switch",
		Service: "turn_off",
		Target: &ServiceTarget{
			EntityID: entityID,
		},
	})
}

// SetTemperature sets the target temperature for a climate entity
func (c *Client) SetTemperature(ctx context.Context, entityID string, temperature float64) error {
	return c.CallService(ctx, &ServiceCall{
		Domain:  "climate",
		Service: "set_temperature",
		Data: map[string]interface{}{
			"temperature": temperature,
		},
		Target: &ServiceTarget{
			EntityID: entityID,
		},
	})
}

// SetHVACMode sets the HVAC mode for a climate entity
func (c *Client) SetHVACMode(ctx context.Context, entityID string, mode string) error {
	return c.CallService(ctx, &ServiceCall{
		Domain:  "climate",
		Service: "set_hvac_mode",
		Data: map[string]interface{}{
			"hvac_mode": mode,
		},
		Target: &ServiceTarget{
			EntityID: entityID,
		},
	})
}

// Ping checks if the Home Assistant API is accessible
func (c *Client) Ping(ctx context.Context) error {
	url := fmt.Sprintf("%s/api/", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.token)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to ping: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	return nil
}
