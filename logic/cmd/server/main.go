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

	// Load integration settings from Redis to override environment variables
	integrationSettings, err := redisClient.HGetAll(ctx, "multizone:integrations")
	if err != nil {
		logger.Warn("Failed to load integration settings from Redis: %v", err)
	} else if len(integrationSettings) > 0 {
		logger.Info("Loading Home Assistant integration settings from Redis...")

		// Override HA settings from Redis if available
		if haEnabled, ok := integrationSettings["ha_enabled"]; ok && haEnabled == "true" {
			cfg.HAEnabled = true

			if haBaseURL, ok := integrationSettings["ha_base_url"]; ok && haBaseURL != "" {
				cfg.HABaseURL = haBaseURL
			}

			if haToken, ok := integrationSettings["ha_token"]; ok && haToken != "" {
				cfg.HAToken = haToken
			}

			if haWebsocket, ok := integrationSettings["ha_websocket"]; ok {
				cfg.HAWebsocket = haWebsocket == "true"
			}

			logger.Info("Loaded HA settings from Redis: Enabled=%v, BaseURL=%s, Websocket=%v",
				cfg.HAEnabled, cfg.HABaseURL, cfg.HAWebsocket)
		} else {
			cfg.HAEnabled = false
			logger.Info("Home Assistant integration disabled in Redis settings")
		}
	}

	// Initialize Home Assistant integration if enabled
	var haIntegration *homeassistant.Integration
	if cfg.HAEnabled && cfg.HAToken != "" {
		logger.Info("Initializing Home Assistant integration...")
		haIntegration = homeassistant.NewIntegration(
			cfg.HABaseURL,
			cfg.HAToken,
			redisClient,
			cfg.HAWebsocket,
		)

		if err := haIntegration.Start(); err != nil {
			logger.Warn("Failed to start Home Assistant integration: %v", err)
			logger.Info("Continuing without Home Assistant integration...")
			haIntegration = nil
		} else {
			logger.Info("Home Assistant integration started successfully")

			// Perform initial state sync
			if err := haIntegration.SyncAllStates(ctx); err != nil {
				logger.Warn("Initial state sync failed: %v", err)
			} else {
				logger.Info("Initial state synchronization completed")
			}
		}
	} else {
		logger.Info("Home Assistant integration is disabled (set HA_ENABLED=true and HA_TOKEN to enable)")
	}

	// Initialize worker pool with processor
	processor := worker.NewProcessor(redisClient, haIntegration)
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
	router.HandleFunc("/api/zones", api.CreateZoneHandler(redisClient, haIntegration)).Methods("POST")
	router.HandleFunc("/api/zones/{id}", api.GetZoneHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/zones/{id}", api.UpdateZoneHandler(redisClient, haIntegration)).Methods("PUT")
	router.HandleFunc("/api/zones/{id}", api.DeleteZoneHandler(redisClient)).Methods("DELETE")

	// Global configuration endpoints
	router.HandleFunc("/api/config", api.GetGlobalConfigHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/config", api.UpdateGlobalConfigHandler(redisClient, haIntegration)).Methods("PUT")

	// Configuration defaults endpoint
	router.HandleFunc("/api/defaults", api.GetDefaultsHandler()).Methods("GET")

	// Integration settings endpoints
	router.HandleFunc("/api/integrations", api.GetIntegrationSettingsHandler(redisClient)).Methods("GET")
	router.HandleFunc("/api/integrations", api.UpdateIntegrationSettingsHandler(redisClient)).Methods("PUT")

	// Temperature calculation endpoints
	router.HandleFunc("/api/calculate", api.CalculateMainTempHandler(redisClient)).Methods("POST")

	// Home Assistant integration endpoints (only if integration is enabled)
	if haIntegration != nil {
		router.HandleFunc("/api/ha/status", api.HAStatusHandler(haIntegration)).Methods("GET")
		router.HandleFunc("/api/ha/test", api.HATestConnectionHandler(haIntegration)).Methods("GET")
		router.HandleFunc("/api/ha/sync", api.HASyncStatesHandler(haIntegration)).Methods("POST")
		router.HandleFunc("/api/ha/entities", api.HAGetEntitiesHandler(haIntegration)).Methods("GET")
		router.HandleFunc("/api/ha/valve", api.HASetValveHandler(haIntegration)).Methods("POST")
		router.HandleFunc("/api/ha/temperature", api.HASetMainTempHandler(haIntegration)).Methods("POST")
		logger.Info("Home Assistant API endpoints registered")
	} else {
		logger.Debug("Home Assistant API endpoints not registered (integration disabled)")
	}

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

	// Stop Home Assistant integration if running
	if haIntegration != nil {
		if err := haIntegration.Stop(); err != nil {
			logger.Error("Error stopping Home Assistant integration: %v", err)
		}
	}

	logger.Info("Server exited")
}
