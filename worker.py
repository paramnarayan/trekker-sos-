from celery import Celery
import time


celery_app = Celery(
    'trekker_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)


@celery_app.task
def trigger_sos(checkpoint_id: str, trek_id: str):
    """
    This function will execute EXACTLY when the grace period expires.
    """
    print(f" WAKING UP: Checking status for Checkpoint {checkpoint_id}...")
    
   
    
    print(f" SOS FIRED for Trek {trek_id}! Alerting emergency contacts.")
    return "SOS_SENT"