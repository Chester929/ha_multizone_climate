package models

// DefaultZoneConfig contains default values for zone configuration
const (
	// DefaultOpeningOffset is the default temperature offset for opening valves
	DefaultOpeningOffset = 0.3

	// DefaultClosingOffset is the default temperature offset for closing valves
	DefaultClosingOffset = 0.3

	// DefaultTargetChangeThreshold is the default threshold for target temperature changes
	DefaultTargetChangeThreshold = 0.1

	// DefaultPriority is the default zone priority
	DefaultPriority = 5
)

// DefaultGlobalConfig contains default values for global configuration
const (
	// DefaultMainTargetAllZonesSatisfied is the default target when all zones are satisfied
	DefaultMainTargetAllZonesSatisfied = 0.5

	// DefaultUseAverageMode determines if average mode is used by default
	DefaultUseAverageMode = false

	// DefaultSliderPosition is the default slider position
	DefaultSliderPosition = 0.5

	// DefaultMinValvesOpen is the default minimum number of valves to keep open
	DefaultMinValvesOpen = 1

	// DefaultMainMinTemp is the default minimum temperature for the main climate
	DefaultMainMinTemp = 18.0

	// DefaultMainMaxTemp is the default maximum temperature for the main climate
	DefaultMainMaxTemp = 30.0

	// DefaultMainChangeThreshold is the default threshold for main temperature changes
	DefaultMainChangeThreshold = 0.5

	// DefaultValveActuationDelay is the default delay between valve actuations in seconds
	DefaultValveActuationDelay = 120

	// DefaultCoordinatorInterval is the default interval for coordinator runs in seconds
	DefaultCoordinatorInterval = 30

	// DefaultSatisfactionEpsilon is the default epsilon for satisfaction calculations
	DefaultSatisfactionEpsilon = 0.0
)
