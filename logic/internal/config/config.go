package config

import (
	"os"
)

// Config holds the application configuration
type Config struct {
	RedisHost     string
	RedisPort     string
	RedisPassword string
	HTTPPort      string
	LogLevel      string
	// Home Assistant API configuration
	HAEnabled    bool
	HABaseURL    string
	HAToken      string
	HAWebsocket  bool
}

// Load loads configuration from environment variables
func Load() *Config {
	return &Config{
		RedisHost:     getEnv("REDIS_HOST", "localhost"),
		RedisPort:     getEnv("REDIS_PORT", "6379"),
		RedisPassword: getEnv("REDIS_PASSWORD", ""),
		HTTPPort:      getEnv("HTTP_PORT", "8080"),
		LogLevel:      getEnv("LOG_LEVEL", "info"),
		HAEnabled:     getEnv("HA_ENABLED", "false") == "true",
		HABaseURL:     getEnv("HA_BASE_URL", "http://homeassistant.local:8123"),
		HAToken:       getEnv("HA_TOKEN", ""),
		HAWebsocket:   getEnv("HA_WEBSOCKET", "true") == "true",
	}
}

func getEnv(key, defaultValue string) string {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}
