import express from 'express';
import cors from 'cors';
import { createClient } from 'redis';
import path from 'path';
import { WebSocketServer } from 'ws';
import { createServer } from 'http';

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
app.use(express.static(path.join(__dirname, '../public')));

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

const clients = new Set<any>();

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
async function broadcastUpdate(type: string, data: any) {
  const message = JSON.stringify({ type, data, timestamp: new Date().toISOString() });
  clients.forEach((client) => {
    if (client.readyState === 1) { // OPEN
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
    const keys = await redisClient.keys('multizone:zone:*');
    const zones = [];
    
    for (const key of keys) {
      const zoneData = await redisClient.hGetAll(key);
      zones.push(zoneData);
    }
    
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

// Zone management endpoints
app.post('/api/zones', async (req, res) => {
  try {
    const zone = req.body;
    const zoneId = zone.id || `zone-${Date.now()}`;
    await redisClient.hSet(`multizone:zone:${zoneId}`, zone);
    await broadcastUpdate('zone-created', { id: zoneId, ...zone });
    res.json({ status: 'created', id: zoneId });
  } catch (error) {
    console.error('Error creating zone:', error);
    res.status(500).json({ error: 'Failed to create zone' });
  }
});

app.put('/api/zones/:id', async (req, res) => {
  try {
    const zoneId = req.params.id;
    const zone = req.body;
    await redisClient.hSet(`multizone:zone:${zoneId}`, zone);
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
    await redisClient.del(`multizone:zone:${zoneId}`);
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
    const hours = parseInt(req.query.hours as string) || 24;
    const limit = Math.min(hours * 60, 1440); // Max 24 hours, 1 per minute
    
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
    const hours = parseInt(req.query.hours as string) || 24;
    const limit = Math.min(hours * 60, 1440);
    
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
  res.sendFile(path.join(__dirname, '../client/index.html'));
});

// Background task to record historical data
async function recordHistoricalData() {
  try {
    const keys = await redisClient.keys('multizone:zone:*');
    const timestamp = new Date().toISOString();
    
    for (const key of keys) {
      const zoneData = await redisClient.hGetAll(key);
      const zoneId = key.replace('multizone:zone:', '');
      const historyEntry = JSON.stringify({
        timestamp,
        current_temperature: zoneData.current_temperature,
        target_temperature: zoneData.target_temperature,
        valve_state: zoneData.valve_state,
        satisfaction: zoneData.satisfaction,
      });
      
      // Keep last 24 hours of data (1440 entries at 1 per minute)
      await redisClient.lPush(`multizone:history:zone:${zoneId}`, historyEntry);
      await redisClient.lTrim(`multizone:history:zone:${zoneId}`, 0, 1439);
    }
    
    // Record system-wide stats
    const systemEntry = JSON.stringify({
      timestamp,
      total_zones: keys.length,
      active_zones: keys.length, // Could filter by enabled zones
    });
    
    await redisClient.lPush('multizone:history:system', systemEntry);
    await redisClient.lTrim('multizone:history:system', 0, 1439);
  } catch (error) {
    console.error('Error recording historical data:', error);
  }
}

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
    setInterval(recordHistoricalData, 60000);
    
    httpServer.listen(PORT, () => {
      console.log(`Frontend server listening on port ${PORT}`);
      console.log(`WebSocket server ready for connections`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

start();
