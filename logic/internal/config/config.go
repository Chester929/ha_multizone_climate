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
}

// Load loads configuration from environment variables
func Load() *Config {
	return &Config{
		RedisHost:     getEnv("REDIS_HOST", "localhost"),
		RedisPort:     getEnv("REDIS_PORT", "6379"),
		RedisPassword: getEnv("REDIS_PASSWORD", ""),
		HTTPPort:      getEnv("HTTP_PORT", "8080"),
		LogLevel:      getEnv("LOG_LEVEL", "info"),
	}
}

func getEnv(key, defaultValue string) string {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}
