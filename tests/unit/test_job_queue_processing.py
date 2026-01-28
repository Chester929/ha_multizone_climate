"""Tests for job queue processing to ensure no data loss."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from custom_components.multizone_climate.coordinator import MultizoneClimateCoordinator
from custom_components.multizone_climate.jobs.base import BaseJob


class MockJob(BaseJob):
    """Mock job for testing."""

    def __init__(self, redis_client, hass):
        super().__init__("test_job", redis_client, hass)
        self.executed_jobs = []

    async def _execute_impl(self, job_data):
        """Mock execute implementation."""
        self.executed_jobs.append(job_data)
        # Simulate some work
        await asyncio.sleep(0.01)
        return {"processed": job_data}


@pytest.mark.asyncio
async def test_job_queue_lock_prevents_dequeue():
    """
    Test that when a lock cannot be acquired, jobs remain in the queue.
    
    This verifies the fix for the race condition where jobs would be
    dequeued before checking the lock, causing data loss.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.acquire_job_lock = AsyncMock()
    mock_redis.release_job_lock = AsyncMock()
    mock_redis.dequeue_job = AsyncMock()
    
    # Mock lock acquisition failure (another worker is processing)
    mock_redis.acquire_job_lock.return_value = False
    
    # Setup mock job data in queue
    mock_redis.dequeue_job.return_value = {"test": "data"}
    
    # Create coordinator with mocked aiohttp session
    mock_hass = MagicMock()
    mock_aiohttp_session = AsyncMock()
    
    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        coordinator = MultizoneClimateCoordinator(
            hass=mock_hass,
            backend_url="http://localhost",
            redis_client=mock_redis
        )
        
        # Create mock job instance
        mock_job = MockJob(mock_redis, mock_hass)
        
        # Process queue - should NOT dequeue because lock fails
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify lock was attempted
        mock_redis.acquire_job_lock.assert_called_once_with("test_job", timeout=60)
        
        # Verify dequeue was NOT called (job stays in queue)
        mock_redis.dequeue_job.assert_not_called()
        
        # Verify job was NOT executed
        assert len(mock_job.executed_jobs) == 0
        
        # Verify lock was NOT released (because it was never acquired)
        mock_redis.release_job_lock.assert_not_called()


@pytest.mark.asyncio
async def test_job_queue_processes_with_lock():
    """
    Test that when lock is acquired, jobs are dequeued and processed.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.acquire_job_lock = AsyncMock(return_value=True)
    mock_redis.release_job_lock = AsyncMock()
    mock_redis.set_job_status = AsyncMock()  # Add this for _update_status
    
    # Mock three jobs in the queue
    jobs = [
        {"job_id": 1, "data": "first"},
        {"job_id": 2, "data": "second"},
        {"job_id": 3, "data": "third"},
        None  # Queue empty
    ]
    mock_redis.dequeue_job = AsyncMock(side_effect=jobs)
    
    # Create coordinator with mocked aiohttp session
    mock_hass = MagicMock()
    mock_aiohttp_session = AsyncMock()
    
    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        coordinator = MultizoneClimateCoordinator(
            hass=mock_hass,
            backend_url="http://localhost",
            redis_client=mock_redis
        )
        
        # Create mock job instance
        mock_job = MockJob(mock_redis, mock_hass)
        
        # Process queue
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify lock was acquired
        mock_redis.acquire_job_lock.assert_called_once_with("test_job", timeout=60)
        
        # Verify all three jobs were dequeued
        assert mock_redis.dequeue_job.call_count == 4  # 3 jobs + 1 None
        
        # Verify all three jobs were executed
        assert len(mock_job.executed_jobs) == 3
        assert mock_job.executed_jobs[0] == {"job_id": 1, "data": "first"}
        assert mock_job.executed_jobs[1] == {"job_id": 2, "data": "second"}
        assert mock_job.executed_jobs[2] == {"job_id": 3, "data": "third"}
        
        # Verify lock was released
        mock_redis.release_job_lock.assert_called_once_with("test_job")


@pytest.mark.asyncio
async def test_job_queue_releases_lock_on_exception():
    """
    Test that lock is released even if job execution fails.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.acquire_job_lock = AsyncMock(return_value=True)
    mock_redis.release_job_lock = AsyncMock()
    mock_redis.set_job_status = AsyncMock()
    
    # Mock one job that will fail
    mock_redis.dequeue_job = AsyncMock(side_effect=[
        {"job_id": 1, "data": "test"},
        None
    ])
    
    # Create coordinator with mocked aiohttp session
    mock_hass = MagicMock()
    mock_aiohttp_session = AsyncMock()
    
    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        coordinator = MultizoneClimateCoordinator(
            hass=mock_hass,
            backend_url="http://localhost",
            redis_client=mock_redis
        )
        
        # Create mock job that raises exception
        mock_job = MockJob(mock_redis, mock_hass)
        
        # Make execute raise an exception
        async def failing_execute(job_data):
            raise ValueError("Simulated failure")
        
        mock_job.execute = failing_execute
        
        # Process queue - should handle exception gracefully
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify lock was acquired
        mock_redis.acquire_job_lock.assert_called_once()
        
        # Verify lock was released even though job failed
        mock_redis.release_job_lock.assert_called_once_with("test_job")


@pytest.mark.asyncio
async def test_multiple_workers_only_one_processes():
    """
    Test that multiple workers don't process the same queue simultaneously.
    
    Simulates two workers trying to process the same job type at the same time.
    Only one should acquire the lock and process jobs.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
    # Track lock state
    lock_held = False
    
    async def mock_acquire_lock(job_type, timeout):
        nonlocal lock_held
        if lock_held:
            return False  # Lock already held
        lock_held = True
        return True
    
    async def mock_release_lock(job_type):
        nonlocal lock_held
        lock_held = False
    
    mock_redis.acquire_job_lock = AsyncMock(side_effect=mock_acquire_lock)
    mock_redis.release_job_lock = AsyncMock(side_effect=mock_release_lock)
    
    # Mock jobs in queue
    jobs = [{"job_id": 1}, {"job_id": 2}, None]
    job_index = 0
    
    async def mock_dequeue(job_type):
        nonlocal job_index
        if job_index < len(jobs):
            result = jobs[job_index]
            job_index += 1
            return result
        return None
    
    mock_redis.dequeue_job = AsyncMock(side_effect=mock_dequeue)
    
    # Create two coordinators (simulating two workers) with mocked aiohttp session
    mock_hass = MagicMock()
    mock_aiohttp_session = AsyncMock()
    
    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        coordinator1 = MultizoneClimateCoordinator(
            hass=mock_hass,
            backend_url="http://localhost",
            redis_client=mock_redis
        )
        coordinator2 = MultizoneClimateCoordinator(
            hass=mock_hass,
            backend_url="http://localhost",
            redis_client=mock_redis
        )
        
        # Create mock jobs
        mock_job1 = MockJob(mock_redis, mock_hass)
        mock_job2 = MockJob(mock_redis, mock_hass)
        
        # Process queue from both workers simultaneously
        await asyncio.gather(
            coordinator1._process_job_queue("test_job", mock_job1),
            coordinator2._process_job_queue("test_job", mock_job2)
        )
        
        # Verify only one worker processed the jobs
        total_executed = len(mock_job1.executed_jobs) + len(mock_job2.executed_jobs)
        assert total_executed == 2  # Both jobs processed
        
        # One worker should have processed both jobs, the other none
        assert (len(mock_job1.executed_jobs) == 2 and len(mock_job2.executed_jobs) == 0) or \
               (len(mock_job1.executed_jobs) == 0 and len(mock_job2.executed_jobs) == 2)


@pytest.mark.asyncio
async def test_job_execute_no_longer_checks_lock():
    """
    Test that BaseJob.execute() no longer checks locks internally.
    
    Locks are now managed at the coordinator level to prevent data loss.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
    # Create mock hass
    mock_hass = MagicMock()
    
    # Create job
    mock_job = MockJob(mock_redis, mock_hass)
    
    # Execute job
    result = await mock_job.execute({"test": "data"})
    
    # Verify job was executed successfully
    assert result["status"] == "completed"
    assert len(mock_job.executed_jobs) == 1
    assert mock_job.executed_jobs[0] == {"test": "data"}
    
    # Note: We don't verify lock operations here because locks
    # are now managed at the coordinator level, not in BaseJob.execute()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
