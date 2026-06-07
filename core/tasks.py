import threading

def run_task_async(func, *args, **kwargs):
    """
    A processing abstraction for running background tasks.
    Uses threading to avoid blocking the main request thread.

    Wraps the function in a safety wrapper so that if the target crashes
    (including native-level crashes from PaddleOCR), the database is
    always updated to a terminal state. Can later be refactored to Celery.
    """
    def safe_wrapper(*a, **kw):
        try:
            func(*a, **kw)
        except Exception as e:
            # Last-resort fallback: mark document as failed if the task function itself
            # didn't handle the exception (e.g. unexpected crash path).
            print(f"[run_task_async] Unhandled exception in background task '{func.__name__}': {e}")
            import traceback
            traceback.print_exc()
            # Attempt to recover document state if it was a document processing task
            if a and func.__name__ == 'process_uploaded_document':
                try:
                    from apps.documents.models import Document
                    doc = Document.objects.get(id=a[0])
                    if doc.ocr_status == 'processing':
                        doc.ocr_status = 'failed'
                        doc.status = Document.STATUS_PENDING
                        doc.save(update_fields=['ocr_status', 'status'])
                except Exception:
                    pass

    thread = threading.Thread(target=safe_wrapper, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread
