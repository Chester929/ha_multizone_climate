package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	redisclient "github.com/chester929/ha_multizone_climate/logic/internal/redis"
	"github.com/go-redis/redis/v8"
)

const (
	// defaultLockTimeoutSeconds is the TTL for distributed locks in seconds.
	// This prevents locks from being held indefinitely if a worker crashes.
	defaultLockTimeoutSeconds = 30

	// workerBackoffDuration is the duration to wait before retrying after an error
	workerBackoffDuration = 1 * time.Second

	// Queue keys
	jobQueueKey        = "multizone:job_queue"
	deadLetterQueueKey = "multizone:dead_letter_queue"
	jobLockKeyPrefix   = "multizone:job_lock:"
	jobStatusKeyPrefix = "multizone:job_status:"
)

// JobType constants define the types of jobs that can be processed
const (
	JobTypeCalculateTemp = "calculate_temp"
	JobTypeUpdateValves  = "update_valves"
	JobTypeSafetyCheck   = "safety_check"
)

// JobProcessor defines the interface for processing different job types
type JobProcessor interface {
	ProcessCalculateTemp(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error)
	ProcessUpdateValves(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error)
	ProcessSafetyCheck(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error)
}

// Pool represents a worker pool for processing background jobs
type Pool struct {
	client     *redisclient.Client
	numWorkers int
	ctx        context.Context
	cancel     context.CancelFunc
	wg         sync.WaitGroup
	processor  JobProcessor
}

// NewPool creates a new worker pool.
// A temporary context is created here to allow EnqueueJob() to be called before Start().
// The context will be replaced when Start() is called with a parent context.
func NewPool(client *redisclient.Client, numWorkers int, processor JobProcessor) *Pool {
	ctx, cancel := context.WithCancel(context.Background())
	return &Pool{
		client:     client,
		numWorkers: numWorkers,
		processor:  processor,
		ctx:        ctx,
		cancel:     cancel,
	}
}

// Start starts the worker pool.
// Can be called multiple times safely - will cancel existing workers and start new ones.
func (p *Pool) Start(parentCtx context.Context) {
	// Cancel existing context and create new one from parent
	if p.cancel != nil {
		p.cancel()
	}
	p.ctx, p.cancel = context.WithCancel(parentCtx)

	for i := 0; i < p.numWorkers; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}

	log.Printf("Started %d workers", p.numWorkers)
}

// Stop stops the worker pool
func (p *Pool) Stop() {
	log.Println("Stopping worker pool...")
	p.cancel()
	p.wg.Wait()
	log.Println("Worker pool stopped")
}

// worker is the main worker goroutine
func (p *Pool) worker(id int) {
	defer p.wg.Done()
	log.Printf("Worker %d started", id)

	for {
		select {
		case <-p.ctx.Done():
			log.Printf("Worker %d stopped", id)
			return
		default:
			// Try to acquire and process a job
			if err := p.processNextJob(id); err != nil {
				// If no job available (redis.Nil), wait a bit before trying again
				if err == redis.Nil {
					select {
					case <-p.ctx.Done():
						return
					case <-time.After(workerBackoffDuration):
						// Wait before checking for jobs again
					}
				} else {
					log.Printf("Worker %d error processing job: %v", id, err)
					time.Sleep(workerBackoffDuration)
				}
			}
		}
	}
}

// processNextJob attempts to pop and process the next job from the queue
func (p *Pool) processNextJob(workerID int) error {
	// Pop job from queue in FIFO order:
	// - Jobs are added to the left (head) with LPush
	// - Jobs are removed from the right (tail) with RPop
	// This ensures the oldest jobs are processed first (FIFO behavior)
	jobData, err := p.client.RPop(p.ctx, jobQueueKey)
	if err != nil {
		return err
	}

	var job models.Job
	if err := json.Unmarshal([]byte(jobData), &job); err != nil {
		log.Printf("Worker %d failed to unmarshal job: %v", workerID, err)

		// Send malformed job data to a dead letter queue so it can be inspected later
		if dlqErr := p.client.LPush(p.ctx, deadLetterQueueKey, jobData); dlqErr != nil {
			log.Printf("Worker %d failed to push job to dead letter queue: %v (original unmarshal error: %v)", workerID, dlqErr, err)
		}

		// Do not propagate the error, as the malformed job has already been removed from the main queue
		return nil
	}

	log.Printf("Worker %d processing job %s (type: %s)", workerID, job.ID, job.Type)

	// Try to acquire distributed lock for this job
	lockKey := jobLockKeyPrefix + job.ID
	lockValue := p.generateLockValue(workerID)
	acquired, err := p.acquireLock(lockKey, lockValue)
	if err != nil {
		log.Printf("Worker %d failed to acquire lock for job %s: %v", workerID, job.ID, err)
		// Re-enqueue the job since we couldn't process it
		if requeueErr := p.EnqueueJob(job); requeueErr != nil {
			log.Printf("Worker %d failed to re-enqueue job %s: %v", workerID, job.ID, requeueErr)
		}
		return err
	}
	if !acquired {
		log.Printf("Worker %d could not acquire lock for job %s (already processing)", workerID, job.ID)
		// Re-enqueue the job since another worker is processing it
		if requeueErr := p.EnqueueJob(job); requeueErr != nil {
			log.Printf("Worker %d failed to re-enqueue job %s: %v", workerID, job.ID, requeueErr)
		}
		return nil
	}
	defer p.releaseLock(lockKey, lockValue)

	// Create job status
	status := models.JobStatus{
		JobID:     job.ID,
		JobType:   job.Type,
		Status:    "running",
		StartedAt: time.Now(),
	}

	// Save initial status
	if err := p.saveJobStatus(status); err != nil {
		log.Printf("Worker %d failed to save initial status for job %s: %v", workerID, job.ID, err)
	}

	// Process the job based on type
	var result map[string]interface{}
	var processingErr error

	if p.processor == nil {
		// If no processor is configured, log and mark as completed
		log.Printf("Worker %d: No processor configured, job %s marked as completed", workerID, job.ID)
		result = map[string]interface{}{"message": "No processor configured"}
		processingErr = nil
	} else {
		// Process with the configured processor
		switch job.Type {
		case JobTypeCalculateTemp:
			result, processingErr = p.processor.ProcessCalculateTemp(p.ctx, job.Params)
		case JobTypeUpdateValves:
			result, processingErr = p.processor.ProcessUpdateValves(p.ctx, job.Params)
		case JobTypeSafetyCheck:
			result, processingErr = p.processor.ProcessSafetyCheck(p.ctx, job.Params)
		default:
			processingErr = fmt.Errorf("unknown job type: %s", job.Type)
		}
	}

	// Update job status
	completedAt := time.Now()
	status.CompletedAt = &completedAt
	status.DurationMs = completedAt.Sub(status.StartedAt).Milliseconds()

	if processingErr != nil {
		status.Status = "failed"
		status.Error = processingErr.Error()
		log.Printf("Worker %d failed to process job %s: %v", workerID, job.ID, processingErr)
	} else {
		status.Status = "completed"
		status.Result = result
		log.Printf("Worker %d completed job %s in %dms", workerID, job.ID, status.DurationMs)
	}

	// Save final status
	if err := p.saveJobStatus(status); err != nil {
		log.Printf("Worker %d failed to save final status for job %s: %v", workerID, job.ID, err)
	}

	return nil
}

// acquireLock attempts to acquire a distributed lock
func (p *Pool) acquireLock(lockKey string, lockValue string) (bool, error) {
	acquired, err := p.client.SetNX(p.ctx, lockKey, lockValue, defaultLockTimeoutSeconds)
	if err != nil {
		return false, err
	}
	return acquired, nil
}

// releaseLock releases a distributed lock by verifying ownership and deleting it.
// This allows quick job reprocessing without waiting for TTL expiration.
func (p *Pool) releaseLock(lockKey string, expectedValue string) error {
	// Get the current lock value
	currentValue, err := p.client.GetString(p.ctx, lockKey)
	if err != nil {
		// Lock might have already expired or been deleted
		if err == redis.Nil {
			return nil
		}
		return err
	}

	// Only delete if we own the lock
	if currentValue == expectedValue {
		return p.client.Del(p.ctx, lockKey)
	}

	// Lock was acquired by another worker (shouldn't happen, but log it)
	log.Printf("Lock ownership mismatch for %s: expected %s, got %s", lockKey, expectedValue, currentValue)
	return nil
}

// saveJobStatus saves the job status to Redis
func (p *Pool) saveJobStatus(status models.JobStatus) error {
	statusKey := jobStatusKeyPrefix + status.JobID
	statusJSON, err := json.Marshal(status)
	if err != nil {
		return err
	}
	return p.client.Set(p.ctx, statusKey, statusJSON)
}

// generateLockValue creates a unique lock value for a worker
func (p *Pool) generateLockValue(workerID int) string {
	return fmt.Sprintf("worker_%d_%d", workerID, time.Now().Unix())
}

// EnqueueJob adds a job to the queue.
// Jobs are added to the left (head) with LPush and removed from the right (tail) with RPop,
// ensuring FIFO (First-In-First-Out) processing order.
func (p *Pool) EnqueueJob(job models.Job) error {
	jobJSON, err := json.Marshal(job)
	if err != nil {
		return err
	}
	return p.client.LPush(p.ctx, jobQueueKey, jobJSON)
}
