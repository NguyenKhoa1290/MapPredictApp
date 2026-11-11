"""Bounded, short-lived preview jobs so slow models do not hold public HTTP open."""
import secrets
import threading
import time

from shared.tabular import PredictionError

LOCK = threading.Lock()
SLOTS = threading.BoundedSemaphore(2)
JOBS = {}
TTL = 120


def prune():
    now = time.monotonic()
    for key, job in list(JOBS.items()):
        if job['finished_at'] is not None and now - job['finished_at'] > TTL:
            del JOBS[key]


def submit(work):
    with LOCK:
        prune()
        # Keep unread results available. Delivered results may be reclaimed
        # under pressure instead of blocking new work for the full TTL.
        for key, job in sorted(JOBS.items(), key=lambda item: item[1].get('delivered_at') or float('inf')):
            if len(JOBS) < 4:
                break
            if job['finished_at'] is not None and job.get('delivered_at') is not None:
                del JOBS[key]
        if len(JOBS) >= 4 or not SLOTS.acquire(blocking=False):
            raise PredictionError('ASSISTANT_BUSY', 'Chatbot đang xử lý yêu cầu, hãy thử lại sau', 429)
        identifier = secrets.token_urlsafe(32)
        JOBS[identifier] = {'finished_at': None, 'result': None}
    def run():
        try:
            result = work()
        except Exception:
            result = ({'error': {'code': 'AI_ERROR', 'message': 'Service AI không thể xử lý yêu cầu'}}, 500)
        finally:
            SLOTS.release()
        with LOCK:
            JOBS[identifier].update(result=result, finished_at=time.monotonic())
    threading.Thread(target=run, name='assistant-preview-job', daemon=True).start()
    return identifier


def poll(identifier):
    with LOCK:
        prune()
        job = JOBS.get(identifier)
        if job is None:
            raise PredictionError('ASSISTANT_JOB_EXPIRED', 'Yêu cầu đã hết hạn hoặc service vừa khởi động lại, hãy gửi lại', 404)
        if job['result'] is not None:
            job['delivered_at'] = time.monotonic()
        return job['result'] or ({'data': {'job_id': identifier, 'state': 'pending'}}, 202)
