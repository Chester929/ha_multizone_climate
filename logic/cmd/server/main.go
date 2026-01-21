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
	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
	"github.com/chester929/ha_multizone_climate/logic/internal/statistics"
	"github.com/chester929/ha_multizone_climate/logic/internal/worker"
	"github.com/gorilla/mux"
)

func main() {
	log.Println("Starting Multizone Climate Logic Container...")

	// Load configuration
	cfg := config.Load()

	// Initialize logger with configured log level
	logger.Init(cfg.LogLevel)

	logger.Info("Loaded configuration: Redis=%s:%s, LogLevel=%s", cfg.RedisHost, cfg.RedisPort, cfg.LogLevel)

	// Initialize Redis client
	ctx := context.Background()
	redisClient, err := redis.NewClient(ctx, cfg)
	if err != nil {
		logger.Fatal("Failed to connect to Redis: %v", err)
	}
	defer redisClient.Close()
	logger.Info("Connected to Redis successfully")

	// Initialize Home Assistant client (optional)
	haClient := homeassistant.NewClient(cfg)
	if haClient != nil {
		logger.Info("Home Assistant client initialized")
	} else {
		logger.Info("Home Assistant client not configured (entity selector will use manual entry)")
	}

	// Initialize worker pool with processor
	processor := worker.NewProcessor(redisClient)
	workerPool := worker.NewPool(redisClient, 5, processor)
	workerPool.Start(ctx)
	logger.Info("Worker pool started")

	// Initialize statistics tracker
	statsTracker := statistics.NewTracker(redisClient)
	logger.Info("Statistics tracker initialized")

	// Create HTTP router
	router := mux.NewRouter()

	// Health and status endpoints
	router.HandleFunc("/health", api.HealthHandler).Methods("GET")
	router.HandleFunc("/status", api.StatusHandler(redisClient)).Methods("GET")
	router.HandleFunc("/metrics", api.MetricsHandler(redisClient)).Methods("GET")

	// Zone management endpoints
	router.HandleFunc("/api/zones", api.ListZonesHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/zones", api.CreateZoneHandler(redisClient, nil)).Methods("POST")
	router.HandleFunc("/api/zones/{id}", api.GetZoneHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/zones/{id}", api.UpdateZoneHandler(redisClient, nil)).Methods("PUT")
	router.HandleFunc("/api/zones/{id}", api.DeleteZoneHandler(redisClient)).Methods("DELETE")

	// Global configuration endpoints
	router.HandleFunc("/api/config", api.GetGlobalConfigHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/config", api.UpdateGlobalConfigHandler(redisClient)).Methods("PUT")

	// Configuration defaults endpoint
	router.HandleFunc("/api/defaults", api.GetDefaultsHandler()).Methods("GET")

	// Home Assistant entities endpoint
	router.HandleFunc("/api/entities", api.GetEntitiesHandler(haClient)).Methods("GET")

	// Integration settings endpoints (for future use if needed)
	router.HandleFunc("/api/integrations", api.GetIntegrationSettingsHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/integrations", api.UpdateIntegrationSettingsHandler(redisClient)).Methods("PUT")

	// Temperature calculation endpoints
	router.HandleFunc("/api/calculate", api.CalculateMainTempHandler(redisClient)).Methods("POST")

	// Statistics endpoints
	router.HandleFunc("/api/statistics/zones/{id}/temperature", api.StatisticsTemperatureHistoryHandler(statsTracker)).Methods("GET")
	router.HandleFunc("/api/statistics/zones/{id}/valve-activity", api.StatisticsValveActivityHandler(statsTracker)).Methods("GET")
	router.HandleFunc("/api/statistics/zones/{id}/energy", api.StatisticsEnergyMetricsHandler(statsTracker)).Methods("GET")
	router.HandleFunc("/api/statistics/zones/{id}/comfort", api.StatisticsComfortMetricsHandler(statsTracker)).Methods("GET")
	router.HandleFunc("/api/statistics/comfort-summary", api.StatisticsAllZonesComfortHandler(statsTracker)).Methods("GET")
	router.HandleFunc("/api/statistics/performance", api.StatisticsPerformanceMetricsHandler(statsTracker)).Methods("GET")
	logger.Info("Statistics API endpoints registered")

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
		logger.Info("HTTP server listening on %s", addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal("HTTP server error: %v", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	logger.Info("Shutting down server...")

	// Graceful shutdown with timeout
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Error("Server forced to shutdown: %v", err)
	}

	workerPool.Stop()

	logger.Info("Server exited")
}
