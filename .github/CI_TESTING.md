# Continuous Integration (CI) Testing

This repository uses GitHub Actions to automatically run tests, linting, and type checking on every push and pull request.

## Workflow File

The CI workflow is defined in `.github/workflows/tests.yml`.

## What Gets Tested

### 1. Code Formatting (Black)
- Ensures all Python code follows consistent formatting standards
- Uses Black code formatter with line length of 88 characters
- Runs on both `custom_components` and `tests` directories

### 2. Linting (Pylint)
- Checks code quality and identifies potential issues
- Runs on `custom_components` directory
- Current target: Score of 9.35/10 or higher

### 3. Type Checking (Mypy)
- Validates type annotations in Python code
- Runs with `continue-on-error: true` due to Home Assistant compatibility issues
- Helps catch type-related bugs early

### 4. Unit Tests (Pytest)
- Runs all unit tests in the `tests/` directory
- Generates code coverage reports
- Tests run on both Python 3.11 and Python 3.12

## Triggering the Workflow

The workflow automatically runs when:
- Code is pushed to `master` or `dev` branches
- A pull request is opened or updated targeting `master` or `dev` branches
- Manually triggered via the Actions tab (workflow_dispatch)

## Local Testing

You can run the same tests locally before pushing:

### Install Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements_dev.txt
```

### Run Black
```bash
# Check formatting
black --check custom_components tests

# Auto-format code
black custom_components tests
```

### Run Pylint
```bash
pylint custom_components
```

### Run Mypy
```bash
mypy custom_components
```

### Run Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=custom_components.multizone_climate --cov-report=term-missing
```

## Test Matrix

The workflow runs tests on multiple Python versions:
- Python 3.11
- Python 3.12

This ensures compatibility across the supported Python versions for Home Assistant.

## Coverage Reports

Coverage reports are generated for Python 3.11 runs and can be uploaded to Codecov if configured.

## Workflow Status

Check the status of the workflow runs:
1. Go to the repository on GitHub
2. Click on the "Actions" tab
3. Select "Tests" from the workflows list
4. View the status of individual runs

## Troubleshooting

### Workflow Fails on Black Check
Run `black custom_components tests` locally to auto-format the code.

### Workflow Fails on Pylint
Review the pylint output and fix the reported issues. Some issues can be suppressed with inline comments if they are false positives.

### Workflow Fails on Tests
Run `pytest tests/ -v` locally to see detailed error messages and fix the failing tests.

### Mypy Errors
Mypy errors are currently set to `continue-on-error: true` and won't fail the workflow. However, it's good practice to fix type annotation issues when possible.

## Best Practices

1. **Run tests locally before pushing** to catch issues early
2. **Format code with Black** to maintain consistency
3. **Keep tests passing** - don't merge PRs with failing tests
4. **Monitor coverage** - aim to maintain or improve code coverage
5. **Review pylint warnings** - fix issues that make sense

## CI Workflow Features

- **Concurrency control**: Cancels in-progress runs when new commits are pushed
- **Caching**: Uses pip caching to speed up dependency installation
- **Matrix testing**: Tests on multiple Python versions
- **Coverage reporting**: Generates and uploads coverage reports
- **Test summary**: Provides a summary of test results at the end
