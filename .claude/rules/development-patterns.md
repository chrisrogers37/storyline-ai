---
paths:
  - "src/**/*.py"
  - "cli/**/*.py"
---

# Development Patterns

## Service Layer Pattern

Services orchestrate business logic and call repositories. They do NOT contain SQL queries or import models directly (except for type hints).

```python
class MyService(BaseService):
    def __init__(self):
        super().__init__()
        self.repo = MyRepository()  # Dependency injection
```

## Service Execution Tracking

All service methods should use `track_execution`:

```python
def my_method(self, param: str):
    with self.track_execution("my_method", input_params={"param": param}) as run_id:
        result = self._do_work(param)
        self.set_result_summary(run_id, {"processed": 1, "success": True})
        return result
```

## Error Handling

Let BaseService handle logging — just raise exceptions:

```python
item = self.repo.get_by_id(item_id)
if not item:
    raise ValueError(f"Item {item_id} not found")
```

## Logging

```python
from src.utils.logger import logger

logger.info(f"Indexing media file: {file_path}")
logger.warning(f"Validation warnings: {warnings}")
logger.error(f"Failed: {error}", exc_info=True)
# Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Image Processing

Instagram Story specs: 9:16 aspect ratio (ideal), 1080x1920 resolution, max 100MB, JPG/PNG/GIF.
Use `ImageProcessor.validate_image()` and `ImageProcessor.optimize_for_instagram()`.

## Security Patterns

- Always `html.escape()` user-supplied values before interpolating into HTML
- Never `allow_origins=["*"]` — restrict to `OAUTH_REDIRECT_BASE_URL`
- Verify signed initData fields match request body fields
- Use Pydantic `Field(ge=, le=)` on all numeric API inputs
