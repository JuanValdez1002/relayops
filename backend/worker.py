import logging
import time

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

import models
from database import SessionLocal
from logging_config import configure_logging


configure_logging()
logger = logging.getLogger("relayops.worker")


POLL_INTERVAL = 2
MAX_RETRIES = 3
STUCK_EVENT_TIMEOUT = 60


def claim_event():
    with SessionLocal() as db:
        with db.begin():
            statement = (
                select(models.Event)
                .where(
                    models.Event.status == "received",
                    or_(
                        models.Event.next_retry_at.is_(None),
                        models.Event.next_retry_at
                        <= datetime.now(timezone.utc),
                    ),
                )
                .order_by(models.Event.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )

            event = db.scalar(statement)

            if event is None:
                return None

            event.status = "processing"
            event.processing_started_at = datetime.now(timezone.utc)

            event_data = {
                "id": event.id,
                "event_type": event.event_type,
                "source": event.source,
                "payload": event.payload,
            }

        logger.info(
            "Event claimed. id=%s type=%s source=%s",
            event_data["id"],
            event_data["event_type"],
            event_data["source"],
        )

        return event_data


def recover_stuck_events():
    cutoff_time = (
        datetime.now(timezone.utc)
        - timedelta(seconds=STUCK_EVENT_TIMEOUT)
    )

    with SessionLocal() as db:
        with db.begin():
            statement = (
                select(models.Event)
                .where(
                    models.Event.status == "processing",
                    models.Event.processing_started_at <= cutoff_time,
                )
                .with_for_update(skip_locked=True)
            )

            events = db.scalars(statement).all()

            for event in events:
                event.retry_count += 1
                event.last_error = "Worker timed out during processing"
                event.processing_started_at = None
                event.next_retry_at = None

                if event.retry_count < MAX_RETRIES:
                    event.status = "received"

                    logger.warning(
                        "Stuck event recovered. id=%s retry=%s status=received",
                        event.id,
                        event.retry_count,
                    )
                else:
                    event.status = "failed"

                    logger.error(
                        "Stuck event reached retry limit. id=%s retries=%s",
                        event.id,
                        event.retry_count,
                    )


def process_event(event):
    """Execute event processing logic."""

    logger.info(
        "Processing event. id=%s type=%s source=%s",
        event["id"],
        event["event_type"],
        event["source"],
    )

    # Test hook. Remove this after testing retries.
    if event["payload"].get("simulate_failure") is True:
        raise RuntimeError("Simulated processing failure")

    logger.info("Event processing completed. id=%s", event["id"])


def mark_event_processed(event_id):
    with SessionLocal() as db:
        event = db.get(models.Event, event_id)

        if event is None:
            logger.warning(
                "Unable to mark event processed. Event not found. id=%s",
                event_id,
            )
            return

        event.status = "processed"
        event.last_error = None
        event.next_retry_at = None
        event.processing_started_at = None

        db.commit()

        logger.info("Event marked as processed. id=%s", event_id)


def handle_event_failure(event_id, error):
    with SessionLocal() as db:
        event = db.get(models.Event, event_id)

        if event is None:
            logger.warning(
                "Unable to record event failure. Event not found. id=%s",
                event_id,
            )
            return

        event.retry_count += 1
        event.last_error = str(error)[:1000]
        event.processing_started_at = None

        retry_delays = {
            1: 5,
            2: 15,
        }

        if event.retry_count < MAX_RETRIES:
            delay = retry_delays[event.retry_count]

            event.status = "received"
            event.next_retry_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=delay)
            )

            logger.warning(
                "Event failed. Retry scheduled. id=%s retry=%s delay=%ss error=%s",
                event_id,
                event.retry_count,
                delay,
                error,
            )

        else:
            event.status = "failed"
            event.next_retry_at = None

            logger.error(
                "Event permanently failed. id=%s retries=%s error=%s",
                event_id,
                event.retry_count,
                error,
            )

        db.commit()


def run_worker():
    logger.info("RelayOps worker started.")
    logger.info("Waiting for events. Poll interval=%ss", POLL_INTERVAL)

    while True:
        recover_stuck_events()
        event = claim_event()

        if event is None:
            time.sleep(POLL_INTERVAL)
            continue

        try:
            process_event(event)
            mark_event_processed(event["id"])

        except Exception as error:
            logger.exception(
                "Event processing raised an exception. id=%s",
                event["id"],
            )
            handle_event_failure(event["id"], error)


if __name__ == "__main__":
    try:
        run_worker()
    except KeyboardInterrupt:
        logger.info("RelayOps worker stopped.")