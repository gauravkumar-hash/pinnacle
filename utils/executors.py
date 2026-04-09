"""
Thread pool executors for background tasks
"""
from concurrent.futures import ThreadPoolExecutor


# Thread pool for background email sending
# Using 2 workers to limit concurrent email operations
email_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email_sender")


def shutdown_executors() -> None:
    """
    Gracefully shutdown all thread pool executors
    Should be called during application shutdown
    """
    email_executor.shutdown(wait=True, cancel_futures=False)
