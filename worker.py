import os

from celery import Celery
from twilio.rest import Client


redis_url = "redis://redis:6379/0"

celery_app = Celery(
    "trekker_tasks",
    broker=redis_url,
    backend=redis_url,
)


@celery_app.task
def send_sms(device_id, latitude, longitude):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
    target_number = "+917017257905"

    client = Client(account_sid, auth_token)
    maps_link = f"https://maps.google.com/?q={latitude},{longitude}"
    message_body = f"URGENT SOS! Trekker device {device_id} triggered an alert. Location: {maps_link}"

    message = client.messages.create(
        body=message_body,
        from_=twilio_phone,
        to=target_number,
    )
    return {"status": "success", "sid": message.sid}