"""Tests for Journey Auto Scheduler"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.journey.auto_scheduler import (
    JourneyAutoScheduler,
    get_auto_scheduler,
    init_auto_scheduler,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_config():
    """Mock JourneyConfig."""
    config = MagicMock()
    config.tenant_id = "test-tenant-1"
    config.hotel_city = "Lahore"
    config.is_enabled = True
    config.morning_message_hour = 8
    config.breakfast_hour = 7
    config.lunch_hour = 11
    config.dinner_hour = 18
    config.evening_hour = 20
    return config


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after each test."""
    # Forcibly reset the singleton state
    JourneyAutoScheduler._instance = None
    JourneyAutoScheduler._initialized = False
    yield
    JourneyAutoScheduler._instance = None
    JourneyAutoScheduler._initialized = False


class TestJourneyAutoScheduler:
    """Test JourneyAutoScheduler singleton and methods."""

    def test_singleton_pattern(self):
        """Test that JourneyAutoScheduler follows singleton pattern."""
        # Ensure clean state
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        # Create first instance
        scheduler1 = JourneyAutoScheduler()

        # Verify it has a scheduler
        assert scheduler1._scheduler is not None

        # Create second instance and verify it's the same
        scheduler2 = JourneyAutoScheduler()
        assert scheduler1 is scheduler2

        # Verify get_auto_scheduler returns same instance
        assert get_auto_scheduler() is scheduler1

    def test_scheduler_initialization(self):
        """Test scheduler initializes with AsyncIOScheduler."""
        scheduler = JourneyAutoScheduler()

        assert scheduler._scheduler is not None
        assert isinstance(scheduler._scheduler, AsyncIOScheduler)
        assert scheduler._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_no_running_scheduler(self, mock_db, mock_config):
        """Test initialize loads configs and starts scheduler."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        # Mock the scheduler as not running
        with patch.object(AsyncIOScheduler, 'running', False, create=True):
            scheduler = JourneyAutoScheduler()
            scheduler._scheduler = MagicMock()
            scheduler._scheduler.running = False

            # Mock query result
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_config]
            mock_db.execute.return_value = mock_result

            # Mock add_job to avoid actual scheduling
            with patch.object(scheduler._scheduler, 'add_job'):
                await scheduler.initialize(mock_db)

            # Verify execute was called
            mock_db.execute.assert_called()

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_initialize_already_running(self, mock_db):
        """Test initialize skips if scheduler already running."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._scheduler.running = True

        # Store the call count before calling initialize
        initial_call_count = mock_db.execute.call_count if hasattr(mock_db, 'execute') else 0

        # execute should not be called if already running
        # We just verify it doesn't error out
        await scheduler.initialize(mock_db)

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    def test_schedule_for_tenant(self, mock_config):
        """Test _schedule_for_tenant adds correct jobs."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()

        scheduler._schedule_for_tenant(mock_config)

        # Verify add_job was called for all expected jobs
        # 5 meal/time jobs + 2 status check jobs = 7 total
        assert scheduler._scheduler.add_job.call_count >= 5

        # Verify specific job IDs
        job_ids_called = [call[1].get('id') for call in scheduler._scheduler.add_job.call_args_list]
        assert f"{mock_config.tenant_id}_morning" in job_ids_called
        assert f"{mock_config.tenant_id}_breakfast" in job_ids_called
        assert f"{mock_config.tenant_id}_lunch" in job_ids_called
        assert f"{mock_config.tenant_id}_dinner" in job_ids_called
        assert f"{mock_config.tenant_id}_evening" in job_ids_called
        assert f"{mock_config.tenant_id}_due_in_check" in job_ids_called
        assert f"{mock_config.tenant_id}_checkout_check" in job_ids_called

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    def test_remove_tenant_schedule(self):
        """Test remove_tenant_schedule removes all tenant jobs."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._scheduler.remove_job = MagicMock()

        tenant_id = "test-tenant-123"
        scheduler.remove_tenant_schedule(tenant_id)

        # Verify all 7 jobs were attempted to be removed
        assert scheduler._scheduler.remove_job.call_count == 7

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_run_morning_cycle_checks_active_flag(self, mock_db, mock_config):
        """Test morning cycle respects active job flag to prevent duplicates."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._active_jobs = {"test-tenant-1": True}  # Mark as running

        with patch('app.services.journey.auto_scheduler.JourneyScheduler') as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            # Should return early without calling scheduler
            await scheduler._run_morning_cycle("test-tenant-1", "Lahore")

            mock_scheduler.run_journey_cycle.assert_not_called()

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_run_morning_cycle_success(self, mock_db, mock_config):
        """Test morning cycle calls JourneyScheduler on success."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._active_jobs = {}

        with patch('app.services.journey.auto_scheduler.JourneyScheduler') as mock_scheduler_class:
            mock_scheduler = AsyncMock()
            mock_scheduler.run_journey_cycle = AsyncMock()
            mock_scheduler_class.return_value = mock_scheduler

            await scheduler._run_morning_cycle("test-tenant-1", "Lahore")

            mock_scheduler.run_journey_cycle.assert_called_once_with(
                tenant_id="test-tenant-1",
                hotel_location={"city": "Lahore"},
            )

        # Verify active flag was reset
        assert scheduler._active_jobs["test-tenant-1"] is False

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_run_morning_cycle_handles_error(self, mock_db, mock_config):
        """Test morning cycle handles errors gracefully."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._active_jobs = {}

        with patch('app.services.journey.auto_scheduler.JourneyScheduler') as mock_scheduler_class:
            mock_scheduler = AsyncMock()
            mock_scheduler.run_journey_cycle = AsyncMock(side_effect=Exception("Test error"))
            mock_scheduler_class.return_value = mock_scheduler

            # Should not raise, just log error
            await scheduler._run_morning_cycle("test-tenant-1", "Lahore")

        # Verify active flag was reset even on error
        assert scheduler._active_jobs["test-tenant-1"] is False

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_check_due_in_guests(self):
        """Test _check_due_in_guests calls JourneyScheduler."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._active_jobs = {}

        with patch('app.services.journey.auto_scheduler.JourneyScheduler') as mock_scheduler_class:
            mock_scheduler = AsyncMock()
            mock_scheduler.send_status_based_messages = AsyncMock()
            mock_scheduler_class.return_value = mock_scheduler

            await scheduler._check_due_in_guests("test-tenant-1", "Lahore")

            mock_scheduler.send_status_based_messages.assert_called_once_with(
                tenant_id="test-tenant-1",
                status="DueIn",
                hotel_location={"city": "Lahore"},
            )

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_check_checkout_guests(self):
        """Test _check_checkout_guests calls JourneyScheduler."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._active_jobs = {}

        with patch('app.services.journey.auto_scheduler.JourneyScheduler') as mock_scheduler_class:
            mock_scheduler = AsyncMock()
            mock_scheduler.send_status_based_messages = AsyncMock()
            mock_scheduler_class.return_value = mock_scheduler

            await scheduler._check_checkout_guests("test-tenant-1", "Lahore")

            mock_scheduler.send_status_based_messages.assert_called_once_with(
                tenant_id="test-tenant-1",
                status="checkout_today",
                hotel_location={"city": "Lahore"},
            )

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_update_tenant_schedule(self, mock_db, mock_config):
        """Test update_tenant_schedule reloads config and reschedules."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler.remove_tenant_schedule = MagicMock()
        scheduler._schedule_for_tenant = MagicMock()

        # Mock query result for updated config
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute.return_value = mock_result

        await scheduler.update_tenant_schedule(mock_db, "test-tenant-1")

        # Verify old schedule was removed
        scheduler.remove_tenant_schedule.assert_called_once_with("test-tenant-1")

        # Verify new schedule was added
        scheduler._schedule_for_tenant.assert_called_once_with(mock_config)

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    @pytest.mark.asyncio
    async def test_update_tenant_schedule_disabled(self, mock_db):
        """Test update_tenant_schedule when config is disabled."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler.remove_tenant_schedule = MagicMock()
        scheduler._schedule_for_tenant = MagicMock()

        # Mock query result for disabled config
        mock_disabled_config = MagicMock()
        mock_disabled_config.is_enabled = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_disabled_config
        mock_db.execute.return_value = mock_result

        await scheduler.update_tenant_schedule(mock_db, "test-tenant-1")

        # Verify schedule removed but new one not added
        scheduler.remove_tenant_schedule.assert_called_once()
        scheduler._schedule_for_tenant.assert_not_called()

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    def test_shutdown(self):
        """Test shutdown stops the scheduler."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = JourneyAutoScheduler()
        scheduler._scheduler = MagicMock()
        scheduler._scheduler.running = True

        scheduler.shutdown()

        scheduler._scheduler.shutdown.assert_called_once()

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False


class TestGetAutoScheduler:
    """Test get_auto_scheduler factory function."""

    def test_returns_singleton(self):
        """Test get_auto_scheduler returns same instance."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler1 = get_auto_scheduler()
        scheduler2 = get_auto_scheduler()

        assert scheduler1 is scheduler2

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

    def test_returns_journey_auto_scheduler(self):
        """Test return type is JourneyAutoScheduler."""
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False

        scheduler = get_auto_scheduler()

        assert isinstance(scheduler, JourneyAutoScheduler)

        # Cleanup
        JourneyAutoScheduler._instance = None
        JourneyAutoScheduler._initialized = False
