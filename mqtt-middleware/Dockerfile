FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY src ./src

# Expose no ports (MQTT client only)

# Run the application
CMD ["node", "src/index.js"]
