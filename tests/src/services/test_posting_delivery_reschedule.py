"""Tests for delivery reschedule logic — REMOVED.

The delivery reschedule feature (reschedule_overdue_for_paused_chat and related
queue rescheduling) was removed as part of the JIT scheduler redesign. In the
JIT model, the posting_queue is an in-flight tracker rather than a pre-populated
schedule, so overdue rescheduling is no longer applicable.

See SchedulerService (src/services/core/scheduler.py) for the replacement
JIT posting logic and its tests in test_scheduler.py.
"""
