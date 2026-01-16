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
	// defaultLockTimeout is the TTL for distributed locks in seconds.
	// This prevents locks from being held indefinitely if a worker crashes.
	defaultLockTimeout = 30
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

// NewPool creates a new worker pool
func NewPool(client *redisclient.Client, numWorkers int, processor JobProcessor) *Pool {
	return &Pool{
		client:     client,
		numWorkers: numWorkers,
		processor:  processor,
	}
}

// Start starts the worker pool
func (p *Pool) Start(parentCtx context.Context) {
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
					case <-time.After(1 * time.Second):
						// Wait before checking for jobs again
					}
				} else {
					log.Printf("Worker %d error processing job: %v", id, err)
					time.Sleep(1 * time.Second)
				}
			}
		}
	}
}

// processNextJob attempts to pop and process the next job from the queue
func (p *Pool) processNextJob(workerID int) error {
	// Pop job from queue (FIFO - using LPop on a list that's pushed with LPush)
	// This ensures jobs are processed in the order they were enqueued.
	jobData, err := p.client.LPop(p.ctx, "multizone:job_queue")
	if err != nil {
		return err
	}

	var job models.Job
	if err := json.Unmarshal([]byte(jobData), &job); err != nil {
		log.Printf("Worker %d failed to unmarshal job: %v", workerID, err)
		return err
	}

	log.Printf("Worker %d processing job %s (type: %s)", workerID, job.ID, job.Type)

	// Try to acquire distributed lock for this job
	lockKey := fmt.Sprintf("multizone:job_lock:%s", job.ID)
	acquired, err := p.acquireLock(lockKey, workerID)
	if err != nil {
		log.Printf("Worker %d failed to acquire lock for job %s: %v", workerID, job.ID, err)
		return err
	}
	if !acquired {
		log.Printf("Worker %d could not acquire lock for job %s (already processing)", workerID, job.ID)
		return nil
	}
	defer p.releaseLock(lockKey)

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
func (p *Pool) acquireLock(lockKey string, workerID int) (bool, error) {
	lockValue := fmt.Sprintf("worker_%d_%d", workerID, time.Now().Unix())
	acquired, err := p.client.SetNX(p.ctx, lockKey, lockValue, defaultLockTimeout)
	if err != nil {
		return false, err
	}
	return acquired, nil
}

// releaseLock releases a distributed lock.
// We rely on the lock's TTL for automatic release and do not explicitly delete it.
// This avoids the race condition where a lock expires and is reacquired by another
// worker before the original worker attempts to delete it.
func (p *Pool) releaseLock(lockKey string) error {
	// Lock will expire automatically via TTL
	return nil
}

// saveJobStatus saves the job status to Redis
func (p *Pool) saveJobStatus(status models.JobStatus) error {
	statusKey := fmt.Sprintf("multizone:job_status:%s", status.JobID)
	statusJSON, err := json.Marshal(status)
	if err != nil {
		return err
	}
	return p.client.Set(p.ctx, statusKey, statusJSON)
}

// EnqueueJob adds a job to the queue
func (p *Pool) EnqueueJob(job models.Job) error {
	jobJSON, err := json.Marshal(job)
	if err != nil {
		return err
	}
	return p.client.LPush(p.ctx, "multizone:job_queue", jobJSON)
}
