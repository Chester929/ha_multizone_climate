import express from 'express';
import cors from 'cors';
import { createClient } from 'redis';
import path from 'path';

const app = express();
const PORT = process.env.WEB_PORT || 8099;

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
    res.json({ status: 'updated' });
  } catch (error) {
    console.error('Error updating config:', error);
    res.status(500).json({ error: 'Failed to update configuration' });
  }
});

// Serve index.html for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/index.html'));
});

// Start server
async function start() {
  try {
    await redisClient.connect();
    console.log('Connected to Redis');
    
    app.listen(PORT, () => {
      console.log(`Frontend server listening on port ${PORT}`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

start();
