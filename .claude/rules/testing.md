---
paths:
  - "tests/**"
  - "conftest.py"
  - "pytest.ini"
---

# Testing Guidelines

## Write Tests for ALL New Functionality

Every new feature must include:

1. **Unit Tests** (`tests/src/`) — Test each service method in isolation, mock all dependencies, fast execution (< 1s per test)
2. **Integration Tests** (`tests/integration/`) — Test service interactions with real database

Test structure mirrors `src/`:
```
tests/
├── src/
│   ├── services/
│   ├── repositories/
│   └── utils/
└── integration/
```

## Test Template

```python
import pytest
from unittest.mock import Mock, patch
from src.services.core.example_service import ExampleService

@pytest.fixture
def example_service():
    service = ExampleService()
    service.repo = Mock()
    return service

class TestExampleService:
    def test_success_case(self, example_service):
        # Arrange
        example_service.repo.get_by_id.return_value = Mock(id=1, name="test")
        # Act
        result = example_service.some_method(1)
        # Assert
        assert result.name == "test"
        example_service.repo.get_by_id.assert_called_once_with(1)

    def test_error_case(self, example_service):
        example_service.repo.get_by_id.side_effect = ValueError("Not found")
        with pytest.raises(ValueError, match="Not found"):
            example_service.some_method(1)
```

## Test Markers

```python
@pytest.mark.unit          # Fast, isolated
@pytest.mark.integration   # Slower, multiple components
@pytest.mark.slow          # Very slow (skip with -m "not slow")
```

## Running Tests

```bash
pytest --cov=src --cov-report=term-missing  # With coverage
pytest -m unit                               # Fast unit tests only
pytest -m "not slow"                         # Exclude slow tests
pytest tests/src/services/test_scheduler.py  # Specific file
```
