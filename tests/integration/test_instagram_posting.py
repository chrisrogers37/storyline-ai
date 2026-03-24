"""Integration tests for Instagram posting workflow.

NOTE: These tests were removed in the JIT scheduler redesign.
The posting flow now goes through SchedulerService.process_slot()
instead of PostingService.process_pending_posts().
"""
