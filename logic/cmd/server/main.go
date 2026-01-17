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
	"github.com/chester929/ha_multizone_climate/logic/internal/homeassistant"
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

	// Initialize Home Assistant integration if enabled
	var haIntegration *homeassistant.Integration
	if cfg.HAEnabled && cfg.HAToken != "" {
		log.Println("Initializing Home Assistant integration...")
		haIntegration = homeassistant.NewIntegration(
			cfg.HABaseURL,
			cfg.HAToken,
			redisClient,
			cfg.HAWebsocket,
		)

		if err := haIntegration.Start(); err != nil {
			log.Printf("Warning: Failed to start Home Assistant integration: %v", err)
			log.Println("Continuing without Home Assistant integration...")
			haIntegration = nil
		} else {
			log.Println("Home Assistant integration started successfully")

			// Perform initial state sync
			if err := haIntegration.SyncAllStates(ctx); err != nil {
				log.Printf("Warning: Initial state sync failed: %v", err)
			} else {
				log.Println("Initial state synchronization completed")
			}
		}
	} else {
		log.Println("Home Assistant integration is disabled (set HA_ENABLED=true and HA_TOKEN to enable)")
	}

	// Initialize worker pool with processor
	processor := worker.NewProcessor(redisClient, haIntegration)
	workerPool := worker.NewPool(redisClient, 5, processor)
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

	// Home Assistant integration endpoints (only if integration is enabled)
	if haIntegration != nil {
		router.HandleFunc("/api/ha/status", api.HAStatusHandler(haIntegration)).Methods("GET")
		router.HandleFunc("/api/ha/test", api.HATestConnectionHandler(haIntegration)).Methods("GET")
		router.HandleFunc("/api/ha/sync", api.HASyncStatesHandler(haIntegration)).Methods("POST")
		router.HandleFunc("/api/ha/valve", api.HASetValveHandler(haIntegration)).Methods("POST")
		router.HandleFunc("/api/ha/temperature", api.HASetMainTempHandler(haIntegration)).Methods("POST")
		log.Println("Home Assistant API endpoints registered")
	}

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

	// Stop Home Assistant integration if running
	if haIntegration != nil {
		if err := haIntegration.Stop(); err != nil {
			log.Printf("Error stopping Home Assistant integration: %v", err)
		}
	}

	log.Println("Server exited")
}
