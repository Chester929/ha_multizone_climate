package redis

import (
	"context"
	"fmt"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/config"
	"github.com/go-redis/redis/v8"
)

// Client wraps the Redis client
type Client struct {
	rdb *redis.Client
}

// NewClient creates a new Redis client
func NewClient(ctx context.Context, cfg *config.Config) (*Client, error) {
	addr := fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort)

	rdb := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: cfg.RedisPassword,
		DB:       0,
	})

	// Test connection
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to ping Redis: %w", err)
	}

	return &Client{rdb: rdb}, nil
}

// Close closes the Redis connection
func (c *Client) Close() error {
	return c.rdb.Close()
}

// Get retrieves a value from Redis
func (c *Client) Get(ctx context.Context, key string) (string, error) {
	return c.rdb.Get(ctx, key).Result()
}

// Set sets a value in Redis
func (c *Client) Set(ctx context.Context, key string, value interface{}) error {
	return c.rdb.Set(ctx, key, value, 0).Err()
}

// HGetAll retrieves all fields and values of a hash
func (c *Client) HGetAll(ctx context.Context, key string) (map[string]string, error) {
	return c.rdb.HGetAll(ctx, key).Result()
}

// HSet sets a field in a hash
func (c *Client) HSet(ctx context.Context, key string, values ...interface{}) error {
	return c.rdb.HSet(ctx, key, values...).Err()
}

// LPush pushes an element to the left of a list
func (c *Client) LPush(ctx context.Context, key string, values ...interface{}) error {
	return c.rdb.LPush(ctx, key, values...).Err()
}

// RPop pops an element from the right of a list
func (c *Client) RPop(ctx context.Context, key string) (string, error) {
	return c.rdb.RPop(ctx, key).Result()
}

// LPop pops an element from the left of a list
func (c *Client) LPop(ctx context.Context, key string) (string, error) {
	return c.rdb.LPop(ctx, key).Result()
}

// Exists checks if a key exists
func (c *Client) Exists(ctx context.Context, keys ...string) (int64, error) {
	return c.rdb.Exists(ctx, keys...).Result()
}

// Del deletes keys
func (c *Client) Del(ctx context.Context, keys ...string) error {
	return c.rdb.Del(ctx, keys...).Err()
}

// Keys returns all keys matching a pattern
func (c *Client) Keys(ctx context.Context, pattern string) ([]string, error) {
	return c.rdb.Keys(ctx, pattern).Result()
}

// Ping checks if Redis is available
func (c *Client) Ping(ctx context.Context) error {
	return c.rdb.Ping(ctx).Err()
}

// SetNX sets a value only if the key does not exist (for distributed locking).
// expirationSeconds specifies the key TTL in seconds.
func (c *Client) SetNX(ctx context.Context, key string, value interface{}, expirationSeconds int) (bool, error) {
	return c.rdb.SetNX(ctx, key, value, time.Duration(expirationSeconds)*time.Second).Result()
}

// GetString retrieves a string value and returns an error if the key doesn't exist
func (c *Client) GetString(ctx context.Context, key string) (string, error) {
	return c.rdb.Get(ctx, key).Result()
}

// HDel deletes one or more hash fields
func (c *Client) HDel(ctx context.Context, key string, fields ...string) error {
	return c.rdb.HDel(ctx, key, fields...).Err()
}

// RDB returns the underlying Redis client for advanced operations
func (c *Client) RDB() *redis.Client {
	return c.rdb
}
