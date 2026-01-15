"""
Simple in-memory job queue for async processing.
For production, replace with Redis Queue (RQ) or Celery.
"""

import threading
import queue
import uuid
from datetime import datetime
from typing import Callable, Any, Dict
import logging

from mochi_analytics.storage.database import get_session
from mochi_analytics.storage.models import Job as JobModel

logger = logging.getLogger(__name__)


class JobQueue:
    """Simple in-memory job queue with worker threads."""

    def __init__(self, num_workers: int = 2):
        """
        Initialize job queue.

        Args:
            num_workers: Number of worker threads to process jobs
        """
        self.queue = queue.Queue()
        self.num_workers = num_workers
        self.workers = []
        self.running = False

    def start(self):
        """Start worker threads."""
        if self.running:
            return

        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)
            logger.info(f"Started worker thread {i}")

    def stop(self):
        """Stop worker threads."""
        self.running = False
        for _ in range(self.num_workers):
            self.queue.put(None)  # Signal workers to stop
        for worker in self.workers:
            worker.join(timeout=5)
        self.workers.clear()
        logger.info("Stopped all worker threads")

    def submit(
        self,
        func: Callable,
        *args,
        job_id: str | None = None,
        **kwargs
    ) -> str:
        """
        Submit a job to the queue.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            job_id: Optional job ID (generates one if not provided)
            **kwargs: Keyword arguments for func

        Returns:
            Job ID
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        job = {
            "id": job_id,
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "submitted_at": datetime.utcnow()
        }

        self.queue.put(job)
        logger.info(f"Submitted job {job_id} to queue")

        return job_id

    def _worker(self, worker_id: int):
        """
        Worker thread that processes jobs from the queue.

        Args:
            worker_id: Worker thread identifier
        """
        logger.info(f"Worker {worker_id} started")

        while self.running:
            try:
                job = self.queue.get(timeout=1)

                if job is None:  # Stop signal
                    break

                job_id = job["id"]
                logger.info(f"Worker {worker_id} processing job {job_id}")

                # Update job status to processing
                session = get_session()
                try:
                    job_model = session.query(JobModel).filter(JobModel.id == job_id).first()
                    if job_model:
                        job_model.status = "processing"
                        session.commit()
                finally:
                    session.close()

                # Execute the job
                try:
                    result = job["func"](*job["args"], **job["kwargs"])

                    # Update job with result
                    session = get_session()
                    try:
                        job_model = session.query(JobModel).filter(JobModel.id == job_id).first()
                        if job_model:
                            job_model.status = "completed"
                            job_model.completed_at = datetime.utcnow()
                            if result is not None:
                                job_model.result = result
                            session.commit()
                            logger.info(f"Job {job_id} completed successfully")
                    finally:
                        session.close()

                except Exception as e:
                    logger.error(f"Job {job_id} failed: {e}", exc_info=True)

                    # Update job with error
                    session = get_session()
                    try:
                        job_model = session.query(JobModel).filter(JobModel.id == job_id).first()
                        if job_model:
                            job_model.status = "failed"
                            job_model.completed_at = datetime.utcnow()
                            job_model.error = str(e)
                            session.commit()
                    finally:
                        session.close()

                finally:
                    self.queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)

        logger.info(f"Worker {worker_id} stopped")


# Global job queue instance
_job_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    """Get the global job queue instance."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue(num_workers=2)
        _job_queue.start()
    return _job_queue


def submit_job(func: Callable, *args, job_id: str | None = None, **kwargs) -> str:
    """
    Submit a job to the global queue (convenience function).

    Args:
        func: Function to execute
        *args: Positional arguments
        job_id: Optional job ID
        **kwargs: Keyword arguments

    Returns:
        Job ID
    """
    queue = get_job_queue()
    return queue.submit(func, *args, job_id=job_id, **kwargs)
