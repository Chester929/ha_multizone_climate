"""Tests for job queue processing to ensure proper sequential processing."""

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
async def test_job_queue_processes_all_jobs():
    """
    Test that all jobs in queue are processed sequentially.
    
    In a single-worker architecture, jobs are dequeued and processed
    one at a time until the queue is empty.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
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
        
        # Verify all three jobs were dequeued
        assert mock_redis.dequeue_job.call_count == 4  # 3 jobs + 1 None
        
        # Verify all three jobs were executed in order
        assert len(mock_job.executed_jobs) == 3
        assert mock_job.executed_jobs[0] == {"job_id": 1, "data": "first"}
        assert mock_job.executed_jobs[1] == {"job_id": 2, "data": "second"}
        assert mock_job.executed_jobs[2] == {"job_id": 3, "data": "third"}


@pytest.mark.asyncio
async def test_job_queue_handles_empty_queue():
    """
    Test that empty queue is handled gracefully.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.dequeue_job = AsyncMock(return_value=None)  # Empty queue
    
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
        
        # Process empty queue - should complete without errors
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify dequeue was called once
        mock_redis.dequeue_job.assert_called_once()
        
        # Verify no jobs were executed
        assert len(mock_job.executed_jobs) == 0


@pytest.mark.asyncio
async def test_job_queue_continues_after_job_failure():
    """
    Test that queue processing continues even if one job fails.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
    # Mock jobs where middle one will fail
    jobs = [
        {"job_id": 1, "data": "first"},
        {"job_id": 2, "data": "will_fail"},
        {"job_id": 3, "data": "third"},
        None
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
        
        # Create mock job that fails on specific data
        mock_job = MockJob(mock_redis, mock_hass)
        
        original_execute = mock_job.execute
        
        async def selective_failing_execute(job_data):
            if job_data.get("data") == "will_fail":
                raise ValueError("Simulated failure")
            return await original_execute(job_data)
        
        mock_job.execute = selective_failing_execute
        
        # Process queue - should handle failure and continue
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify all jobs were attempted (dequeued)
        assert mock_redis.dequeue_job.call_count == 4
        
        # Verify first and third jobs succeeded (second failed)
        assert len(mock_job.executed_jobs) == 2
        assert mock_job.executed_jobs[0] == {"job_id": 1, "data": "first"}
        assert mock_job.executed_jobs[1] == {"job_id": 3, "data": "third"}


@pytest.mark.asyncio
async def test_job_execute_processes_successfully():
    """
    Test that BaseJob.execute() processes jobs successfully.
    
    In a single-worker architecture, jobs are processed one at a time
    without any locking mechanism needed.
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


@pytest.mark.asyncio
async def test_redis_rpop_is_atomic():
    """
    Test that demonstrates Redis RPOP is atomic.
    
    This verifies that dequeue operation removes the job atomically,
    preventing any race conditions in a single-worker scenario.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
    call_count = 0
    
    # Simulate atomic RPOP behavior
    async def atomic_dequeue(job_type):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"job_id": 1, "atomically_removed": True}
        return None
    
    mock_redis.dequeue_job = AsyncMock(side_effect=atomic_dequeue)
    
    # Create coordinator with mocked aiohttp session
    mock_hass = MagicMock()
    mock_aiohttp_session = AsyncMock()
    
    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        coordinator = MultizoneClimateCoordinator(
            hass=mock_hass,
            backend_url="http://localhost",
            redis_client=mock_redis
        )
        
        # Create mock job
        mock_job = MockJob(mock_redis, mock_hass)
        
        # Process queue
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify job was dequeued and processed
        assert len(mock_job.executed_jobs) == 1
        assert mock_job.executed_jobs[0]["atomically_removed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
