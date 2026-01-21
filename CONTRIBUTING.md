# Contributing to Multizone Climate

Thank you for your interest in contributing to the Multizone Climate project! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
   ```bash
   git clone https://github.com/your-username/ha_multizone_climate.git
   cd ha_multizone_climate
   ```
3. **Set up development environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

## Development Workflow

### Prerequisites

- **Docker and Docker Compose**: For running containers
- **Go 1.21+**: For GoLang development
- **Python 3.11+**: For custom integration development
- **Make**: For using the Makefile commands
- **Home Assistant**: For testing the custom integration

### Running Locally

```bash
# Start all services
make start

# View logs
make logs

# Stop services
make stop
```

### Development Mode

**Logic Container (GoLang):**
```bash
cd logic
go run cmd/server/main.go
```

**Custom Integration (Python):**
```bash
# Copy to your Home Assistant config directory
cp -r custom_components/multizone_climate /path/to/ha/config/custom_components/
# Restart Home Assistant to load changes
```

## Code Standards

### GoLang

- Follow standard Go formatting (`gofmt`)
- Use `go vet` for linting
- Write tests for all algorithms and business logic
- Use meaningful variable and function names
- Add comments for exported functions

**Example:**
```go
// CalculateMainTargetTemperature calculates the main thermostat target temperature
// based on all zone states and configuration. It returns the new target temperature
// and a boolean indicating whether the target should be updated.
func CalculateMainTargetTemperature(zones []models.ZoneState, config models.GlobalConfig, currentTarget float64) (float64, bool) {
    // Implementation...
}
```

### TypeScript

- Use TypeScript strict mode
- Follow ESLint rules
- Use meaningful variable and function names
- Add JSDoc comments for complex functions

**Example:**
```typescript
/**
 * Fetches zone data from Redis
 * @returns Promise resolving to array of zones
 */
async function fetchZones(): Promise<Zone[]> {
    // Implementation...
}
```

### Python

- Follow PEP 8 style guide
- Use type hints for function parameters and returns
- Write docstrings for classes and methods
- Follow Home Assistant integration guidelines

**Example:**
```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Multizone Climate entities from a config entry."""
    # Implementation...
```

### Testing

- **GoLang**: Write unit tests using the standard `testing` package
  ```bash
  cd logic
  go test ./...
  ```

- **Python**: Write tests for the custom integration
  ```bash
  # Run Home Assistant test suite if applicable
  pytest tests/
  ```

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, concise commit messages
   - Keep commits focused and atomic
   - Add tests for new functionality

3. **Test your changes**
   ```bash
   make test-logic
   # Test custom integration in Home Assistant
   ```

4. **Lint your code**
   ```bash
   make lint-logic
   # For Python: ruff check custom_components/multizone_climate/
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**
   - Provide a clear description of the changes
   - Reference any related issues
   - Ensure CI checks pass

### Pull Request Guidelines

- **Title**: Use a clear, descriptive title
- **Description**: Explain what changes were made and why
- **Testing**: Describe how the changes were tested
- **Documentation**: Update documentation if needed
- **Breaking Changes**: Clearly mark any breaking changes

## Commit Message Format

Use conventional commit format:

```
type(scope): subject

body

footer
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(logic): add valve priority sorting algorithm

Implements priority-based valve selection for safety checks.
Valves with higher priority are preferred when enforcing
minimum open valve requirements.

Closes #123
```

```
fix(frontend): correct zone temperature display rounding

Temperature values are now correctly rounded to 0.5°C
increments for display consistency.
```

## Code Review Process

1. At least one maintainer must review and approve the PR
2. CI checks must pass
3. Code must follow project standards
4. Tests must be included for new features
5. Documentation must be updated if needed

## Architecture Guidelines

### Adding New Features

When adding new features, consider:

1. **Separation of Concerns**: Which container should handle this feature?
2. **Data Flow**: How does data flow between containers?
3. **Redis Schema**: Does this require new Redis keys?
4. **API Design**: What API endpoints are needed?
5. **Testing**: How will this be tested?

### Container Responsibilities

- **Logic Container**: Core algorithms, business logic, safety checks, REST API
- **Custom Integration**: HA entities, config flow, coordinator, state synchronization

### Redis Data Organization

Follow the existing schema pattern:
```
multizone:<type>:<id>:<field>
```

Examples:
- `multizone:config` - Global configuration
- `multizone:zone:bedroom` - Zone state
- `multizone:queue:calculate_main_temp` - Job queue

## Documentation

### Code Documentation

- Add comments for complex logic
- Document all exported functions
- Update DIAGRAMS.md if architecture changes
- Update IMPLEMENTATION.md for new features

### User Documentation

- Update README.md for user-facing changes
- Update hassio-addon/README.md for add-on changes
- Update custom_components/multizone_climate/README.md for integration changes
- Add examples for new features

## Reporting Issues

When reporting issues, include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Detailed steps to reproduce
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**: 
   - OS and version
   - Docker version
   - Home Assistant version (if applicable)
6. **Logs**: Relevant log output
7. **Screenshots**: If applicable

## Feature Requests

Feature requests are welcome! Please:

1. Check if the feature already exists or is planned
2. Clearly describe the feature and its use case
3. Explain why it would be beneficial
4. Consider implementation approach (optional)

## Community Guidelines

- Be respectful and constructive
- Help others when possible
- Follow the code of conduct
- Keep discussions focused and on-topic

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (see [LICENSE](LICENSE)).

## Questions?

If you have questions about contributing:

- Open a [Discussion](https://github.com/Chester929/ha_multizone_climate/discussions)
- Create an [Issue](https://github.com/Chester929/ha_multizone_climate/issues)
- Check existing documentation

Thank you for contributing to Multizone Climate! 🌡️
