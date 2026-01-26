---
description: "Run tests and fix any failures"
---

1. Run the test suite: `pytest tests/ -v --tb=short`
2. If all tests pass, report success
3. If tests fail:
   - Analyze each failure carefully
   - Identify the root cause (is it the test or the implementation?)
   - Fix the issue
   - Re-run tests to verify the fix
   - Repeat until all tests pass

For faster iteration on specific areas:
- `pytest tests/src/services/ -v` - Service tests
- `pytest tests/src/repositories/ -v` - Repository tests
- `pytest tests/integration/ -v` - Integration tests
- `pytest -m unit -v` - All unit tests only
- `pytest -k "test_name"` - Run specific test by name

Coverage check:
- `pytest --cov=src --cov-report=term-missing`

Be methodical: fix one test at a time and verify before moving to the next.

**SAFETY REMINDER**: Tests should never actually post to Instagram. Verify mocks are in place.
