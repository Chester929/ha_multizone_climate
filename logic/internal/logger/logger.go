package logger

import (
	"fmt"
	"log"
	"os"
	"strings"
)

// LogLevel represents the severity of a log message
type LogLevel int

const (
	// DEBUG level for detailed diagnostic information
	DEBUG LogLevel = iota
	// INFO level for general informational messages
	INFO
	// WARN level for warning messages
	WARN
	// ERROR level for error messages
	ERROR
)

var (
	currentLevel LogLevel = INFO
	levelNames   = map[LogLevel]string{
		DEBUG: "DEBUG",
		INFO:  "INFO",
		WARN:  "WARN",
		ERROR: "ERROR",
	}
	// ANSI color codes for different log levels
	levelColors = map[LogLevel]string{
		DEBUG: "\033[36m", // Cyan
		INFO:  "\033[32m", // Green
		WARN:  "\033[33m", // Yellow
		ERROR: "\033[31m", // Red
	}
	colorReset = "\033[0m"
)

// Init initializes the logger with the specified log level from string
func Init(levelStr string) {
	levelStr = strings.ToUpper(strings.TrimSpace(levelStr))
	switch levelStr {
	case "DEBUG":
		currentLevel = DEBUG
	case "INFO":
		currentLevel = INFO
	case "WARN", "WARNING":
		currentLevel = WARN
	case "ERROR":
		currentLevel = ERROR
	default:
		currentLevel = INFO
		log.Printf("Unknown log level '%s', defaulting to INFO", levelStr)
	}
	log.Printf("Log level set to: %s", levelNames[currentLevel])
}

// SetLevel sets the current log level
func SetLevel(level LogLevel) {
	currentLevel = level
}

// GetLevel returns the current log level
func GetLevel() LogLevel {
	return currentLevel
}

// logMessage logs a message at the specified level
func logMessage(level LogLevel, format string, args ...interface{}) {
	if level < currentLevel {
		return
	}

	// Check if we should use colors (when output is a terminal)
	useColors := isTerminal()
	
	var prefix string
	if useColors {
		prefix = fmt.Sprintf("%s[%s]%s", levelColors[level], levelNames[level], colorReset)
	} else {
		prefix = fmt.Sprintf("[%s]", levelNames[level])
	}

	message := fmt.Sprintf(format, args...)
	log.Printf("%s %s", prefix, message)
}

// isTerminal checks if stdout is a terminal
func isTerminal() bool {
	fileInfo, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return (fileInfo.Mode() & os.ModeCharDevice) != 0
}

// Debug logs a debug message
func Debug(format string, args ...interface{}) {
	logMessage(DEBUG, format, args...)
}

// Info logs an info message
func Info(format string, args ...interface{}) {
	logMessage(INFO, format, args...)
}

// Warn logs a warning message
func Warn(format string, args ...interface{}) {
	logMessage(WARN, format, args...)
}

// Error logs an error message
func Error(format string, args ...interface{}) {
	logMessage(ERROR, format, args...)
}

// Fatal logs an error message and exits
func Fatal(format string, args ...interface{}) {
	logMessage(ERROR, format, args...)
	os.Exit(1)
}
