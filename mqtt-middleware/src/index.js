const mqtt = require('mqtt');
const { createClient } = require('redis');
const logger = require('./logger');

logger.info('Starting MQTT Middleware...');

// Configuration from environment
const config = {
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD || undefined,
    database: parseInt(process.env.REDIS_DB || '0'),
  },
  mqtt: {
    broker: process.env.MQTT_BROKER || 'homeassistant.local',
    port: parseInt(process.env.MQTT_PORT || '1883'),
    username: process.env.MQTT_USERNAME || undefined,
    password: process.env.MQTT_PASSWORD || undefined,
  },
  discoveryPrefix: process.env.MQTT_DISCOVERY_PREFIX || 'homeassistant',
  topicPrefix: process.env.MQTT_TOPIC_PREFIX || 'multizone',
};

// Redis client
const redisClient = createClient({
  socket: {
    host: config.redis.host,
    port: config.redis.port,
  },
  password: config.redis.password,
  database: config.redis.database,
});

redisClient.on('error', (err) => logger.error('Redis Client Error:', err));

// MQTT client
const mqttClient = mqtt.connect(`mqtt://${config.mqtt.broker}:${config.mqtt.port}`, {
  username: config.mqtt.username,
  password: config.mqtt.password,
  clientId: 'multizone-mqtt-middleware',
  clean: true,
  reconnectPeriod: 5000,
});

mqttClient.on('connect', () => {
  logger.info('Connected to MQTT broker');
  
  // Subscribe to command topics
  mqttClient.subscribe(`${config.topicPrefix}/climate/+/set`, (err) => {
    if (err) logger.error('Subscribe error:', err);
  });
  
  mqttClient.subscribe(`${config.topicPrefix}/climate/+/target_temperature/set`, (err) => {
    if (err) logger.error('Subscribe error:', err);
  });
  
  // Publish online status
  mqttClient.publish(`${config.topicPrefix}/status`, 'online', { retain: true });
});

mqttClient.on('message', async (topic, message) => {
  logger.debug(`Received MQTT message on ${topic}: ${message.toString()}`);
  
  try {
    // Parse topic to extract zone ID
    const topicParts = topic.split('/');
    const zoneId = topicParts[2];
    
    if (topic.endsWith('/target_temperature/set')) {
      // Update target temperature in Redis
      const temperature = parseFloat(message.toString());
      await redisClient.hSet(`multizone:zone:${zoneId}`, 'target_temperature', temperature);
      logger.debug(`Updated zone ${zoneId} target temperature to ${temperature}`);
    } else if (topic.endsWith('/set')) {
      // Update mode or other settings
      const data = JSON.parse(message.toString());
      await redisClient.hSet(`multizone:zone:${zoneId}`, data);
      logger.debug(`Updated zone ${zoneId} settings`);
    }
  } catch (error) {
    logger.error('Error processing MQTT message:', error);
  }
});

mqttClient.on('error', (err) => {
  logger.error('MQTT Client Error:', err);
});

mqttClient.on('close', () => {
  logger.info('MQTT connection closed');
});

// Redis Pub/Sub for state changes
async function subscribeToRedisChanges() {
  const subscriber = redisClient.duplicate();
  await subscriber.connect();
  
  // Subscribe to zone state changes
  await subscriber.pSubscribe('__keyspace@0__:multizone:zone:*', (message, channel) => {
    logger.debug(`Redis key change: ${channel}`);
    
    // Extract zone ID from channel
    const keyMatch = channel.match(/multizone:zone:(\w+)/);
    if (keyMatch) {
      const zoneId = keyMatch[1];
      publishZoneState(zoneId);
    }
  });
  
  logger.info('Subscribed to Redis keyspace notifications');
}

async function publishZoneState(zoneId) {
  try {
    const zoneData = await redisClient.hGetAll(`multizone:zone:${zoneId}`);
    
    if (Object.keys(zoneData).length === 0) {
      return;
    }
    
    // Publish state to MQTT
    const stateTopic = `${config.topicPrefix}/climate/${zoneId}/state`;
    mqttClient.publish(stateTopic, JSON.stringify({
      mode: zoneData.mode || 'heat',
      current_temperature: parseFloat(zoneData.current_temperature) || 0,
      target_temperature: parseFloat(zoneData.target_temperature) || 20,
      satisfaction: zoneData.satisfaction || 'unknown',
      valve_state: zoneData.valve_state || 'unknown',
      enabled: zoneData.enabled === 'true',
    }), { retain: true });
    
    logger.debug(`Published state for zone ${zoneId}`);
  } catch (error) {
    logger.error(`Error publishing zone state for ${zoneId}:`, error);
  }
}

async function publishDiscovery() {
  try {
    // Get all zones
    const zoneKeys = await redisClient.keys('multizone:zone:*');
    
    for (const key of zoneKeys) {
      const zoneId = key.replace('multizone:zone:', '');
      const zoneData = await redisClient.hGetAll(key);
      
      // Publish discovery config for climate entity
      const discoveryTopic = `${config.discoveryPrefix}/climate/multizone_${zoneId}/config`;
      const discoveryPayload = {
        name: zoneData.name || zoneId,
        unique_id: `multizone_${zoneId}_climate`,
        device: {
          identifiers: [`multizone_${zoneId}`],
          name: zoneData.name || zoneId,
          model: 'Multizone Climate v2.0',
          manufacturer: 'Multizone Climate',
        },
        temperature_state_topic: `${config.topicPrefix}/climate/${zoneId}/state`,
        temperature_command_topic: `${config.topicPrefix}/climate/${zoneId}/target_temperature/set`,
        current_temperature_topic: `${config.topicPrefix}/climate/${zoneId}/state`,
        current_temperature_template: '{{ value_json.current_temperature }}',
        temperature_state_template: '{{ value_json.target_temperature }}',
        mode_state_topic: `${config.topicPrefix}/climate/${zoneId}/state`,
        mode_state_template: '{{ value_json.mode }}',
        modes: ['off', 'heat', 'cool'],
        temperature_unit: 'C',
        min_temp: 15,
        max_temp: 30,
        temp_step: 0.5,
      };
      
      mqttClient.publish(discoveryTopic, JSON.stringify(discoveryPayload), { retain: true });
      logger.debug(`Published discovery for zone ${zoneId}`);
    }
  } catch (error) {
    logger.error('Error publishing discovery:', error);
  }
}

// Start the middleware
async function start() {
  try {
    await redisClient.connect();
    logger.info('Connected to Redis');
    
    // Wait for MQTT connection
    await new Promise((resolve) => {
      if (mqttClient.connected) {
        resolve();
      } else {
        mqttClient.on('connect', resolve);
      }
    });
    
    // Subscribe to Redis changes
    await subscribeToRedisChanges();
    
    // Wait for MQTT connection to be stable before publishing discovery
    let retries = 0;
    const maxRetries = 10;
    while (!mqttClient.connected && retries < maxRetries) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      retries++;
    }
    
    if (mqttClient.connected) {
      await publishDiscovery();
      logger.info('MQTT Discovery published successfully');
    } else {
      logger.warn('MQTT not connected, discovery will be published on next connection');
    }
    
    logger.info('MQTT Middleware running');
  } catch (error) {
    logger.error('Failed to start middleware:', error);
    process.exit(1);
  }
}

start();

// Graceful shutdown
process.on('SIGINT', () => {
  logger.info('Shutting down...');
  mqttClient.end();
  redisClient.quit();
  process.exit(0);
});
