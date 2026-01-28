"""Tests for reliable job queue processing with error handling."""

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
    
    Jobs are peeked at, processed, then removed on success.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
    # Mock peek and remove operations
    jobs = [
        {"job_id": 1, "data": "first"},
        {"job_id": 2, "data": "second"},
        {"job_id": 3, "data": "third"},
        None  # Queue empty
    ]
    job_index = 0
    
    async def mock_peek(job_type):
        nonlocal job_index
        if job_index < len(jobs):
            return jobs[job_index]
        return None
    
    async def mock_remove(job_type, job_data):
        nonlocal job_index
        job_index += 1
        return True
    
    mock_redis.peek_job = AsyncMock(side_effect=mock_peek)
    mock_redis.remove_job = AsyncMock(side_effect=mock_remove)
    
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
        
        # Verify all three jobs were peeked
        assert mock_redis.peek_job.call_count == 4  # 3 jobs + 1 None
        
        # Verify all three jobs were removed after processing
        assert mock_redis.remove_job.call_count == 3
        
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
    mock_redis.peek_job = AsyncMock(return_value=None)  # Empty queue
    
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
        
        # Verify peek was called once
        mock_redis.peek_job.assert_called_once()
        
        # Verify no jobs were executed
        assert len(mock_job.executed_jobs) == 0


@pytest.mark.asyncio
async def test_job_failure_moves_to_error_queue():
    """
    Test that failed jobs are moved to error queue instead of being lost.
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
    job_index = 0
    
    async def mock_peek(job_type):
        nonlocal job_index
        if job_index < len(jobs):
            return jobs[job_index]
        return None
    
    async def mock_remove(job_type, job_data):
        nonlocal job_index
        job_index += 1
        return True
    
    async def mock_move_to_error(job_type, job_data, error):
        nonlocal job_index
        # Moving to error queue also increments the index (job removed from queue)
        job_index += 1
    
    mock_redis.peek_job = AsyncMock(side_effect=mock_peek)
    mock_redis.remove_job = AsyncMock(side_effect=mock_remove)
    mock_redis.move_job_to_error_queue = AsyncMock(side_effect=mock_move_to_error)
    
    # Create coordinator with mocked aiohttp session
    mock_hass = MagicMock()
    mock_aiohttp_session = AsyncMock()
    
    with patch("aiohttp.ClientSession", return_value=mock_aiohttp_session):
        coordinator = MultizoneClimateCoordinator(
            hass=mock_hass,
            backend_url="http://localhost",
            redis_client=mock_redis
        )
        
        # Create mock job that returns failure for specific data
        mock_job = MockJob(mock_redis, mock_hass)
        
        original_execute = mock_job.execute
        
        async def selective_failing_execute(job_data):
            if job_data.get("data") == "will_fail":
                return {"status": "failed", "error": "Simulated failure"}
            return await original_execute(job_data)
        
        mock_job.execute = selective_failing_execute
        
        # Process queue
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify all jobs were attempted (peeked)
        assert mock_redis.peek_job.call_count == 4
        
        # Verify failed job was moved to error queue
        mock_redis.move_job_to_error_queue.assert_called_once()
        call_args = mock_redis.move_job_to_error_queue.call_args
        assert call_args[0][0] == "test_job"  # job_type
        assert call_args[0][1] == {"job_id": 2, "data": "will_fail"}  # job_data
        assert "Simulated failure" in call_args[0][2]  # error
        
        # Verify successful jobs were removed normally
        assert mock_redis.remove_job.call_count == 2
        
        # Verify first and third jobs succeeded (second failed)
        assert len(mock_job.executed_jobs) == 2
        assert mock_job.executed_jobs[0] == {"job_id": 1, "data": "first"}
        assert mock_job.executed_jobs[1] == {"job_id": 3, "data": "third"}


@pytest.mark.asyncio
async def test_job_exception_moves_to_error_queue():
    """
    Test that jobs that raise exceptions are moved to error queue.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
    # Mock one job that will raise exception
    jobs = [
        {"job_id": 1, "data": "will_crash"},
        None
    ]
    job_index = 0
    
    async def mock_peek(job_type):
        nonlocal job_index
        if job_index < len(jobs):
            return jobs[job_index]
        return None
    
    async def mock_remove(job_type, job_data):
        nonlocal job_index
        job_index += 1
        return True
    
    async def mock_move_to_error(job_type, job_data, error):
        nonlocal job_index
        # Moving to error queue also increments the index (job removed from queue)
        job_index += 1
    
    mock_redis.peek_job = AsyncMock(side_effect=mock_peek)
    mock_redis.remove_job = AsyncMock(side_effect=mock_remove)
    mock_redis.move_job_to_error_queue = AsyncMock(side_effect=mock_move_to_error)
    
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
        
        async def crashing_execute(job_data):
            raise ValueError("Simulated crash")
        
        mock_job.execute = crashing_execute
        
        # Process queue - should handle exception gracefully
        await coordinator._process_job_queue("test_job", mock_job)
        
        # Verify job was moved to error queue with exception message
        mock_redis.move_job_to_error_queue.assert_called_once()
        call_args = mock_redis.move_job_to_error_queue.call_args
        assert "Simulated crash" in call_args[0][2]  # error message


@pytest.mark.asyncio
async def test_job_not_removed_until_successful():
    """
    Test that jobs remain in queue until successfully processed.
    
    This ensures restart resilience - if addon crashes during processing,
    job will still be in queue when restarted.
    """
    # Setup mock redis client
    mock_redis = MagicMock()
    mock_redis.set_job_status = AsyncMock()
    
    job_data = {"job_id": 1, "important": "data"}
    peek_count = 0
    remove_called = False
    
    async def mock_peek(job_type):
        nonlocal peek_count, remove_called
        peek_count += 1
        # Job should be available until remove is called
        if not remove_called:
            return job_data
        return None
    
    async def mock_remove(job_type, data):
        nonlocal remove_called
        remove_called = True
        return True
    
    mock_redis.peek_job = AsyncMock(side_effect=mock_peek)
    mock_redis.remove_job = AsyncMock(side_effect=mock_remove)
    
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
        
        # Verify job was peeked first
        assert peek_count >= 1
        
        # Verify job was executed
        assert len(mock_job.executed_jobs) == 1
        
        # Verify job was removed AFTER successful execution
        assert remove_called
        mock_redis.remove_job.assert_called_once_with("test_job", job_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
