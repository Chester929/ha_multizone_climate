// Simple structured logger for Node.js

const LOG_LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3
};

const LEVEL_NAMES = {
  0: 'DEBUG',
  1: 'INFO',
  2: 'WARN',
  3: 'ERROR'
};

const LEVEL_COLORS = {
  0: '\x1b[36m', // Cyan
  1: '\x1b[32m', // Green
  2: '\x1b[33m', // Yellow
  3: '\x1b[31m'  // Red
};

const RESET_COLOR = '\x1b[0m';

class Logger {
  constructor() {
    // Get log level from environment variable, default to INFO
    const levelStr = (process.env.LOG_LEVEL || 'INFO').toUpperCase();
    this.currentLevel = LOG_LEVELS[levelStr] !== undefined ? LOG_LEVELS[levelStr] : LOG_LEVELS.INFO;
    
    // Check if we should use colors (when output is a TTY)
    this.useColors = process.stdout.isTTY || false;
    
    console.log(`Log level set to: ${LEVEL_NAMES[this.currentLevel]}`);
  }

  log(level, message, ...args) {
    if (level < this.currentLevel) {
      return;
    }

    const timestamp = new Date().toISOString();
    const levelName = LEVEL_NAMES[level];
    
    let prefix;
    if (this.useColors) {
      prefix = `${LEVEL_COLORS[level]}[${levelName}]${RESET_COLOR}`;
    } else {
      prefix = `[${levelName}]`;
    }

    const formattedMessage = args.length > 0 
      ? message.replace(/%s/g, () => args.shift())
      : message;

    console.log(`${timestamp} ${prefix} ${formattedMessage}`, ...args);
  }

  debug(message, ...args) {
    this.log(LOG_LEVELS.DEBUG, message, ...args);
  }

  info(message, ...args) {
    this.log(LOG_LEVELS.INFO, message, ...args);
  }

  warn(message, ...args) {
    this.log(LOG_LEVELS.WARN, message, ...args);
  }

  error(message, ...args) {
    this.log(LOG_LEVELS.ERROR, message, ...args);
  }
}

module.exports = new Logger();
