import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Attempt
from .services import finalize_attempt_locked


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="apps.attempts.tasks.finalize_expired_attempts",
    max_retries=3,
)
def finalize_expired_attempts(self, batch_size=200):

    now = timezone.now()

    expired_ids = list(
        Attempt.objects.filter(
            status=Attempt.Status.IN_PROGRESS,
            deadline_at__lte=now,
        )
        .order_by("deadline_at")
        .values_list("id", flat=True)[:batch_size]
    )

    completed = 0
    skipped = 0
    failed = 0

    for attempt_id in expired_ids:
        try:
            with transaction.atomic():

                attempt = (
                    Attempt.objects
                    .select_for_update()
                    .filter(
                        pk=attempt_id,
                        status=Attempt.Status.IN_PROGRESS,
                        deadline_at__lte=now,
                    )
                    .first()
                )

                if attempt is None:
                    skipped += 1
                    continue

                finalize_attempt_locked(
                    attempt,
                    now=now,
                )

                completed += 1

        except Exception:
            failed += 1

            logger.exception(
                "Failed to finalize expired attempt %s",
                attempt_id,
            )

    logger.info(
        "Expired attempts processed: scanned=%s completed=%s skipped=%s failed=%s",
        len(expired_ids),
        completed,
        skipped,
        failed,
    )

    return {
        "scanned": len(expired_ids),
        "completed": completed,
        "skipped": skipped,
        "failed": failed,
    }