import express from 'express';
import cors from 'cors';
import { createClient } from 'redis';
import path from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { createServer } from 'http';

interface ZoneData {
  id?: string;
  name?: string;
  enabled?: string;
  current_temperature?: string;
  target_temperature?: string;
  satisfaction?: string;
  valve_state?: string;
  priority?: string;
  temperature_sensor_entity_id?: string;
  valve_switch_entity_id?: string;
  climate_entity_id?: string;
}

interface BroadcastData {
  id?: string;
  [key: string]: unknown;
}

const app = express();
const PORT = process.env.WEB_PORT || 8099;
const LOGIC_API_URL = process.env.LOGIC_API_URL || 'http://logic:8080';
const httpServer = createServer(app);

// Hop-by-hop headers that should not be forwarded in proxied requests
// Based on RFC 7230 Section 6.1
const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

// Validate and parse Redis port
function parseRedisPort(portStr: string | undefined): number {
  const defaultPort = 6379;
  if (!portStr) {
    return defaultPort;
  }
  
  const port = parseInt(portStr, 10);
  
  if (isNaN(port)) {
    console.error(`Invalid REDIS_PORT value: "${portStr}". Must be a valid number. Using default port ${defaultPort}.`);
    return defaultPort;
  }
  
  if (port < 1 || port > 65535) {
    console.error(`Invalid REDIS_PORT value: ${port}. Must be between 1 and 65535. Using default port ${defaultPort}.`);
    return defaultPort;
  }
  
  return port;
}

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'client')));

// Redis client
const redisPort = parseRedisPort(process.env.REDIS_PORT);
const redisClient = createClient({
  socket: {
    host: process.env.REDIS_HOST || 'localhost',
    port: redisPort,
  },
  password: process.env.REDIS_PASSWORD || undefined,
});

redisClient.on('error', (err) => console.error('Redis Client Error', err));

// WebSocket Server
const wss = new WebSocketServer({ server: httpServer });

const clients = new Set<WebSocket>();

wss.on('connection', (ws) => {
  console.log('WebSocket client connected');
  clients.add(ws);
  
  ws.on('close', () => {
    console.log('WebSocket client disconnected');
    clients.delete(ws);
  });
  
  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
    clients.delete(ws);
  });
});

// Broadcast function for real-time updates
async function broadcastUpdate(type: string, data: BroadcastData) {
  const message = JSON.stringify({ type, data, timestamp: new Date().toISOString() });
  clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
}

// Subscribe to Redis pub/sub for real-time updates
const subscriber = redisClient.duplicate();
subscriber.on('error', (err) => console.error('Redis Subscriber Error', err));

// Health endpoint
app.get('/health', async (req, res) => {
  try {
    // Verify Redis connection
    await redisClient.ping();
    res.json({ status: 'healthy', redis: 'connected', time: new Date().toISOString() });
  } catch (error) {
    res.status(503).json({ status: 'unhealthy', redis: 'disconnected', time: new Date().toISOString() });
  }
});

// Proxy for Home Assistant API endpoints to logic container
app.all('/api/ha/*', async (req, res) => {
  try {
    const path = req.path;
    const queryString = req.originalUrl.split('?')[1];
    const url = `${LOGIC_API_URL}${path}${queryString ? `?${queryString}` : ''}`;
    
    // Forward relevant headers from the original request, excluding hop-by-hop headers
    const forwardedHeaders: Record<string, string> = {};
    for (const [headerName, headerValue] of Object.entries(req.headers)) {
      if (!headerValue) continue;
      const lowerName = headerName.toLowerCase();
      if (HOP_BY_HOP_HEADERS.has(lowerName)) continue;
      // Skip host header - fetch API will set it correctly for the target
      if (lowerName === 'host') continue;
      if (Array.isArray(headerValue)) {
        forwardedHeaders[headerName] = headerValue.join(', ');
      } else {
        forwardedHeaders[headerName] = String(headerValue);
      }
    }

    // Set JSON content type for HA endpoints (all HA endpoints use JSON)
    forwardedHeaders['content-type'] = 'application/json';
    
    const fetchOptions: RequestInit = {
      method: req.method,
      headers: forwardedHeaders,
    };
    
    // Forward body for POST/PUT/PATCH requests
    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body) {
      fetchOptions.body = JSON.stringify(req.body);
    }
    
    const response = await fetch(url, fetchOptions);
    
    // Forward response headers from logic container, excluding hop-by-hop headers
    response.headers.forEach((value, key) => {
      if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
        res.setHeader(key, value);
      }
    });
    
    // Check if response is JSON before parsing
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      const data = await response.json();
      res.status(response.status).json(data);
    } else {
      // For non-JSON responses, return as text
      const text = await response.text();
      res.status(response.status).send(text);
    }
  } catch (error) {
    console.error('Error proxying to logic container:', error);
    res.status(503).json({ 
      error: 'Logic container unavailable',
      message: 'Unable to connect to logic container. Please ensure it is running and reachable.'
    });
  }
});

// API endpoints
app.get('/api/zones', async (req, res) => {
  try {
    const zones = [];
    let cursor = 0;
    
    // Use SCAN instead of KEYS for better performance
    do {
      const result = await redisClient.scan(cursor, {
        MATCH: 'multizone:zone:*',
        COUNT: 100
      });
      cursor = result.cursor;
      
      for (const key of result.keys) {
        const zoneData = await redisClient.hGetAll(key);
        zones.push(zoneData);
      }
    } while (cursor !== 0);
    
    res.json(zones);
  } catch (error) {
    console.error('Error fetching zones:', error);
    res.status(500).json({ error: 'Failed to fetch zones' });
  }
});

app.get('/api/config', async (req, res) => {
  try {
    const config = await redisClient.hGetAll('multizone:config');
    res.json(config);
  } catch (error) {
    console.error('Error fetching config:', error);
    res.status(500).json({ error: 'Failed to fetch configuration' });
  }
});

app.put('/api/config', async (req, res) => {
  try {
    const config = req.body;
    await redisClient.hSet('multizone:config', config);
    await broadcastUpdate('config', config);
    res.json({ status: 'updated' });
  } catch (error) {
    console.error('Error updating config:', error);
    res.status(500).json({ error: 'Failed to update configuration' });
  }
});

// Integration settings endpoints
app.get('/api/integrations', async (req, res) => {
  try {
    const settings = await redisClient.hGetAll('multizone:integrations');
    
    // Apply defaults for missing values
    if (!settings.ha_websocket || settings.ha_websocket === '') {
      settings.ha_websocket = 'true';
    }
    
    // Mask sensitive fields when returning settings
    const maskedSettings = { ...settings };
    if (maskedSettings.ha_token && maskedSettings.ha_token.trim() !== '') {
      maskedSettings.ha_token = '••••••••';
    }
    if (maskedSettings.mqtt_password && maskedSettings.mqtt_password.trim() !== '') {
      maskedSettings.mqtt_password = '••••••••';
    }
    
    res.json(maskedSettings);
  } catch (error) {
    console.error('Error fetching integration settings:', error);
    res.status(500).json({ error: 'Failed to fetch integration settings' });
  }
});

// Allowed configuration keys for integration settings
const INTEGRATION_CONFIG_KEYS = [
  'ha_enabled', 'ha_base_url', 'ha_token', 'ha_websocket',
  'mqtt_enabled', 'mqtt_broker', 'mqtt_port', 'mqtt_username', 'mqtt_password'
];

app.put('/api/integrations', async (req, res) => {
  try {
    const settings = req.body;
    
    // Get existing settings to merge with update (for partial updates when masked fields are omitted)
    const existingSettings = await redisClient.hGetAll('multizone:integrations');
    
    // Merge new settings with existing (new settings take precedence)
    const mergedSettings = { ...existingSettings, ...settings };
    
    // Validate settings structure
    for (const key of Object.keys(settings)) {
      if (!INTEGRATION_CONFIG_KEYS.includes(key)) {
        return res.status(400).json({ error: `Invalid setting key: ${key}` });
      }
      
      // All values must be strings
      if (typeof settings[key] !== 'string') {
        return res.status(400).json({ error: `Setting ${key} must be a string` });
      }
    }
    
    // Check if both HA and MQTT are enabled (mutual exclusion)
    const haEnabled = mergedSettings.ha_enabled === 'true';
    const mqttEnabled = mergedSettings.mqtt_enabled === 'true';
    
    if (haEnabled && mqttEnabled) {
      return res.status(400).json({ 
        error: 'Cannot enable both Home Assistant and MQTT integrations simultaneously. Please disable one before enabling the other.' 
      });
    }
    
    // Validate HA settings if enabled
    if (mergedSettings.ha_enabled === 'true') {
      if (!mergedSettings.ha_base_url || mergedSettings.ha_base_url.trim() === '') {
        return res.status(400).json({ error: 'HA base URL is required when HA is enabled' });
      }
      if (!mergedSettings.ha_token || mergedSettings.ha_token.trim() === '') {
        return res.status(400).json({ error: 'HA access token is required when HA is enabled' });
      }
    } else {
      // Clear HA settings when disabled to avoid confusion
      delete mergedSettings.ha_base_url;
      delete mergedSettings.ha_token;
      delete mergedSettings.ha_websocket;
    }
    
    // Validate MQTT settings if enabled
    if (mergedSettings.mqtt_enabled === 'true') {
      if (!mergedSettings.mqtt_broker || mergedSettings.mqtt_broker.trim() === '') {
        return res.status(400).json({ error: 'MQTT broker is required when MQTT is enabled' });
      }
      // Ensure MQTT port is set; default to 1883 if omitted
      let mqttPort = (mergedSettings.mqtt_port || '').trim();
      if (mqttPort === '') {
        mqttPort = '1883';
      }
      const port = parseInt(mqttPort, 10);
      if (isNaN(port) || port < 1 || port > 65535) {
        return res.status(400).json({ error: 'MQTT port must be between 1 and 65535' });
      }
      // Persist the normalized port value back to settings
      mergedSettings.mqtt_port = mqttPort;
    } else {
      // Clear MQTT settings when disabled to avoid confusion
      delete mergedSettings.mqtt_broker;
      delete mergedSettings.mqtt_port;
      delete mergedSettings.mqtt_username;
      delete mergedSettings.mqtt_password;
    }
    
    await redisClient.hSet('multizone:integrations', mergedSettings);
    await broadcastUpdate('integrations', mergedSettings);
    
    // Check if HA-related settings changed (check if properties exist in the request)
    const haSettingsChanged = 'ha_enabled' in settings || 
                              'ha_base_url' in settings || 
                              'ha_token' in settings || 
                              'ha_websocket' in settings;
    
    if (haSettingsChanged) {
      console.log('HA integration settings changed. Please restart the logic container for changes to take effect.');
    }
    
    res.json({ status: 'updated' });
  } catch (error) {
    console.error('Error updating integration settings:', error);
    res.status(500).json({ error: 'Failed to update integration settings' });
  }
});


// Zone management endpoints
app.post('/api/zones', async (req, res) => {
  try {
    const zone: ZoneData = req.body;
    
    // Validate required fields
    if (!zone.name || zone.name.trim() === '') {
      return res.status(400).json({ error: 'Zone name is required' });
    }
    
    const zoneId = zone.id || `zone-${Date.now()}`;
    
    // Validate zone ID format (alphanumeric, hyphens, underscores only)
    if (!/^[a-zA-Z0-9_-]+$/.test(zoneId)) {
      return res.status(400).json({ error: 'Zone ID must contain only alphanumeric characters, hyphens, and underscores' });
    }
    
    // Validate entity IDs if provided
    if (zone.temperature_sensor_entity_id && !/^[a-z_]+\.[a-z0-9_]+$/.test(zone.temperature_sensor_entity_id)) {
      return res.status(400).json({ error: 'Invalid temperature sensor entity ID format, expected format: domain.entity_name' });
    }
    
    if (zone.valve_switch_entity_id && !/^[a-z_]+\.[a-z0-9_]+$/.test(zone.valve_switch_entity_id)) {
      return res.status(400).json({ error: 'Invalid valve switch entity ID format, expected format: domain.entity_name' });
    }
    
    if (zone.climate_entity_id && !/^[a-z_]+\.[a-z0-9_]+$/.test(zone.climate_entity_id)) {
      return res.status(400).json({ error: 'Invalid climate entity ID format, expected format: domain.entity_name' });
    }
    
    // Validate target temperature if provided
    if (zone.target_temperature) {
      const temp = parseFloat(zone.target_temperature);
      if (isNaN(temp) || temp < -50 || temp > 100) {
        return res.status(400).json({ error: 'Target temperature must be between -50 and 100' });
      }
    }
    
    // Validate priority if provided
    if (zone.priority) {
      const priority = parseInt(zone.priority, 10);
      if (isNaN(priority) || priority < 0 || priority > 100) {
        return res.status(400).json({ error: 'Priority must be between 0 and 100' });
      }
    }
    
    const zoneData: ZoneData = {
      id: zoneId,
      name: zone.name,
      enabled: zone.enabled || 'true',
      target_temperature: zone.target_temperature || '20',
      current_temperature: zone.current_temperature || 'N/A',
      satisfaction: zone.satisfaction || 'unknown',
      valve_state: zone.valve_state || 'closed',
      priority: zone.priority || '0',
      temperature_sensor_entity_id: zone.temperature_sensor_entity_id || '',
      valve_switch_entity_id: zone.valve_switch_entity_id || '',
      climate_entity_id: zone.climate_entity_id || '',
    };
    
    await redisClient.hSet(`multizone:zone:${zoneId}`, zoneData as Record<string, string>);
    await broadcastUpdate('zone-created', { id: zoneId, ...zoneData });
    res.json({ status: 'created', id: zoneId });
  } catch (error) {
    console.error('Error creating zone:', error);
    res.status(500).json({ error: 'Failed to create zone' });
  }
});

app.put('/api/zones/:id', async (req, res) => {
  try {
    const zoneId = req.params.id;
    const zone: ZoneData = req.body;
    
    // Validate zone ID format
    if (!zoneId || zoneId.trim() === '' || !/^[a-zA-Z0-9_-]+$/.test(zoneId)) {
      return res.status(400).json({ error: 'Invalid zone ID format' });
    }
    
    // Validate zone name if provided
    if (zone.name !== undefined && zone.name.trim() === '') {
      return res.status(400).json({ error: 'Zone name cannot be empty' });
    }
    
    // Validate numeric fields if provided
    if (zone.target_temperature !== undefined) {
      const temp = parseFloat(zone.target_temperature);
      if (isNaN(temp) || temp < -50 || temp > 100) {
        return res.status(400).json({ error: 'Target temperature must be between -50 and 100' });
      }
    }
    
    if (zone.priority !== undefined) {
      const priority = parseInt(zone.priority, 10);
      if (isNaN(priority) || priority < 0 || priority > 100) {
        return res.status(400).json({ error: 'Priority must be between 0 and 100' });
      }
    }
    
    // Check if zone exists
    const exists = await redisClient.exists(`multizone:zone:${zoneId}`);
    if (!exists) {
      return res.status(404).json({ error: 'Zone not found' });
    }
    
    await redisClient.hSet(`multizone:zone:${zoneId}`, zone as Record<string, string>);
    await broadcastUpdate('zone-updated', { id: zoneId, ...zone });
    res.json({ status: 'updated' });
  } catch (error) {
    console.error('Error updating zone:', error);
    res.status(500).json({ error: 'Failed to update zone' });
  }
});

app.delete('/api/zones/:id', async (req, res) => {
  try {
    const zoneId = req.params.id;
    
    // Validate zone ID format
    if (!zoneId || zoneId.trim() === '' || !/^[a-zA-Z0-9_-]+$/.test(zoneId)) {
      return res.status(400).json({ error: 'Invalid zone ID format' });
    }
    
    // Check if zone exists
    const exists = await redisClient.exists(`multizone:zone:${zoneId}`);
    if (!exists) {
      return res.status(404).json({ error: 'Zone not found' });
    }
    
    // Delete zone and its history
    await redisClient.del(`multizone:zone:${zoneId}`);
    await redisClient.del(`multizone:history:zone:${zoneId}`);
    await broadcastUpdate('zone-deleted', { id: zoneId });
    res.json({ status: 'deleted' });
  } catch (error) {
    console.error('Error deleting zone:', error);
    res.status(500).json({ error: 'Failed to delete zone' });
  }
});

// Historical data endpoints
app.get('/api/history/zones/:id', async (req, res) => {
  try {
    const zoneId = req.params.id;
    
    // Validate zone ID format
    if (!zoneId || zoneId.trim() === '' || !/^[a-zA-Z0-9_-]+$/.test(zoneId)) {
      return res.status(400).json({ error: 'Invalid zone ID format' });
    }
    
    const hours = parseInt(req.query.hours as string, 10) || 24;
    
    // Validate hours parameter (max 168 hours = 1 week)
    if (hours < 1 || hours > 168) {
      return res.status(400).json({ error: 'Hours parameter must be between 1 and 168' });
    }
    
    const limit = Math.min(hours * 60, 168 * 60); // Max 168 hours, 1 per minute
    
    const history = await redisClient.lRange(`multizone:history:zone:${zoneId}`, 0, limit - 1);
    const parsed = history.map(h => JSON.parse(h));
    
    res.json(parsed);
  } catch (error) {
    console.error('Error fetching zone history:', error);
    res.status(500).json({ error: 'Failed to fetch zone history' });
  }
});

app.get('/api/history/system', async (req, res) => {
  try {
    const hours = parseInt(req.query.hours as string, 10) || 24;
    
    // Validate hours parameter (max 168 hours = 1 week)
    if (hours < 1 || hours > 168) {
      return res.status(400).json({ error: 'Hours parameter must be between 1 and 168' });
    }
    
    const limit = Math.min(hours * 60, 168 * 60); // Max 168 hours, 1 per minute
    
    const history = await redisClient.lRange('multizone:history:system', 0, limit - 1);
    const parsed = history.map(h => JSON.parse(h));
    
    res.json(parsed);
  } catch (error) {
    console.error('Error fetching system history:', error);
    res.status(500).json({ error: 'Failed to fetch system history' });
  }
});

// Serve index.html for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'client', 'index.html'));
});

// Background task to record historical data
async function recordHistoricalData() {
  try {
    const zones: string[] = [];
    let cursor = 0;
    
    // Use SCAN instead of KEYS for better performance
    do {
      const result = await redisClient.scan(cursor, {
        MATCH: 'multizone:zone:*',
        COUNT: 100
      });
      cursor = result.cursor;
      zones.push(...result.keys);
    } while (cursor !== 0);
    
    const timestamp = new Date().toISOString();
    
    for (const key of zones) {
      const zoneData = await redisClient.hGetAll(key);
      const zoneId = key.replace('multizone:zone:', '');
      
      // Only record if we have valid zone data
      if (Object.keys(zoneData).length === 0) {
        continue;
      }
      
      const historyEntry = JSON.stringify({
        timestamp,
        current_temperature: zoneData.current_temperature || null,
        target_temperature: zoneData.target_temperature || null,
        valve_state: zoneData.valve_state || null,
        satisfaction: zoneData.satisfaction || null,
      });
      
      // Keep last 168 hours of data (10080 entries at 1 per minute)
      await redisClient.lPush(`multizone:history:zone:${zoneId}`, historyEntry);
      await redisClient.lTrim(`multizone:history:zone:${zoneId}`, 0, 10079);
    }
    
    // Record system-wide stats
    const systemEntry = JSON.stringify({
      timestamp,
      total_zones: zones.length,
      active_zones: zones.length, // Could filter by enabled zones
    });
    
    await redisClient.lPush('multizone:history:system', systemEntry);
    await redisClient.lTrim('multizone:history:system', 0, 10079); // Keep last 168 hours of data (10080 entries at 1 per minute)
  } catch (error) {
    console.error('Error recording historical data:', error);
  }
}

let historicalDataInterval: NodeJS.Timeout | null = null;

// Start server
async function start() {
  try {
    await redisClient.connect();
    console.log('Connected to Redis');
    
    await subscriber.connect();
    console.log('Connected to Redis subscriber');
    
    // Subscribe to zone updates
    await subscriber.subscribe('multizone:zone:updates', (message) => {
      try {
        const data = JSON.parse(message);
        broadcastUpdate('zone-update', data);
      } catch (error) {
        console.error('Error parsing zone update:', error);
      }
    });
    
    // Start recording historical data every minute
    historicalDataInterval = setInterval(recordHistoricalData, 60000);
    
    httpServer.listen(PORT, () => {
      console.log(`Frontend server listening on port ${PORT}`);
      console.log(`WebSocket server ready for connections`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Cleanup function
async function cleanup() {
  console.log('Shutting down server...');
  if (historicalDataInterval) {
    clearInterval(historicalDataInterval);
  }
  
  // Close WebSocket server gracefully
  if (wss) {
    await new Promise<void>((resolve) => {
      wss.close(() => {
        console.log('WebSocket server closed');
        resolve();
      });
    });
  }
  
  // Close HTTP server gracefully
  if (httpServer) {
    await new Promise<void>((resolve) => {
      httpServer.close(() => {
        console.log('HTTP server closed');
        resolve();
      });
    });
  }
  
  // Close Redis connections
  try {
    await redisClient.quit();
    console.log('Redis client closed');
  } catch (error) {
    console.error('Error closing Redis client:', error);
  }
  
  try {
    await subscriber.quit();
    console.log('Redis subscriber closed');
  } catch (error) {
    console.error('Error closing Redis subscriber:', error);
  }
  
  process.exit(0);
}

process.on('SIGTERM', cleanup);
process.on('SIGINT', cleanup);

start();
