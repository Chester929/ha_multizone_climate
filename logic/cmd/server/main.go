package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/api"
	"github.com/chester929/ha_multizone_climate/logic/internal/config"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
	"github.com/chester929/ha_multizone_climate/logic/internal/worker"
	"github.com/gorilla/mux"
)

func main() {
	log.Println("Starting Multizone Climate Logic Container...")

	// Load configuration
	cfg := config.Load()
	log.Printf("Loaded configuration: Redis=%s:%s, LogLevel=%s", cfg.RedisHost, cfg.RedisPort, cfg.LogLevel)

	// Initialize Redis client
	ctx := context.Background()
	redisClient, err := redis.NewClient(ctx, cfg)
	if err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	defer redisClient.Close()
	log.Println("Connected to Redis successfully")

	// Initialize worker pool
	// Passing nil for processor as a placeholder - in a full implementation,
	// this would be a struct implementing the JobProcessor interface
	workerPool := worker.NewPool(redisClient, 5, nil)
	workerPool.Start(ctx)
	log.Println("Worker pool started")

	// Create HTTP router
	router := mux.NewRouter()

	// Health and status endpoints
	router.HandleFunc("/health", api.HealthHandler).Methods("GET")
	router.HandleFunc("/status", api.StatusHandler(redisClient)).Methods("GET")
	router.HandleFunc("/metrics", api.MetricsHandler(redisClient)).Methods("GET")

	// Zone management endpoints
	router.HandleFunc("/api/zones", api.ListZonesHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/zones/{id}", api.GetZoneHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/zones/{id}", api.UpdateZoneHandler(redisClient)).Methods("PUT")

	// Temperature calculation endpoints
	router.HandleFunc("/api/calculate", api.CalculateMainTempHandler(redisClient)).Methods("POST")

	// Create HTTP server
	addr := fmt.Sprintf(":%s", cfg.HTTPPort)
	srv := &http.Server{
		Addr:         addr,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in a goroutine
	go func() {
		log.Printf("HTTP server listening on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP server error: %v", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	// Graceful shutdown with timeout
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Server forced to shutdown: %v", err)
	}

	workerPool.Stop()
	log.Println("Server exited")
}
