import logging
import uuid
from datetime import timedelta

from celery import shared_task
from django.utils.timezone import now

from users.models import EmailVerification, User

logger = logging.getLogger(__name__)

@shared_task
def send_email_verification(user_id):
    user = User.objects.get(id=user_id)
    expiration = now() + timedelta(hours=48)
    record = EmailVerification.objects.create(code=uuid.uuid4(), user=user, expiration=expiration)
    record.send_verification_email()

# @shared_task
# def test_task():
#     #logger.info("Starting test_task")
#     try:
#         print("Task executed")
#         #logger.info("Task executed successfully")
#         return "Task executed"
#     except Exception as e:
#         #logger.error(f"Task execution failed: {e}")
#         raise e