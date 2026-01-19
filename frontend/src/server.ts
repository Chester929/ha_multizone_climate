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
}

interface BroadcastData {
  id?: string;
  [key: string]: unknown;
}

const app = express();
const PORT = process.env.WEB_PORT || 8099;
const httpServer = createServer(app);

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
    res.json(settings);
  } catch (error) {
    console.error('Error fetching integration settings:', error);
    res.status(500).json({ error: 'Failed to fetch integration settings' });
  }
});

app.put('/api/integrations', async (req, res) => {
  try {
    const settings = req.body;
    await redisClient.hSet('multizone:integrations', settings);
    await broadcastUpdate('integrations', settings);
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
    
    const zoneData: ZoneData = {
      id: zoneId,
      name: zone.name,
      enabled: zone.enabled || 'true',
      target_temperature: zone.target_temperature || '20',
      current_temperature: zone.current_temperature || 'N/A',
      satisfaction: zone.satisfaction || 'unknown',
      valve_state: zone.valve_state || 'closed',
      priority: zone.priority || '0',
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
