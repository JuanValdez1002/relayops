
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
import worker
from database import Base


@pytest.fixture
def worker_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    monkeypatch.setattr(worker, "SessionLocal", TestSession)

    yield TestSession

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_event(
    db,
    event_id="worker-test-event",
    status="received",
    retry_count=0,
    payload=None,
    processing_started_at=None,
):
    event = models.Event(
        id=event_id,
        event_type="order.created",
        source="pytest-worker",
        payload=payload or {},
        status=status,
        created_at=datetime.now(timezone.utc),
        retry_count=retry_count,
        processing_started_at=processing_started_at,
    )

    db.add(event)
    db.commit()

    return event


def test_claim_event_returns_none_when_queue_empty(worker_db):
    result = worker.claim_event()

    assert result is None


def test_claim_event_updates_event_status(worker_db):
    with worker_db() as db:
        create_event(db)

    result = worker.claim_event()

    assert result is not None
    assert result["id"] == "worker-test-event"
    assert result["event_type"] == "order.created"
    assert result["source"] == "pytest-worker"

    with worker_db() as db:
        event = db.get(models.Event, "worker-test-event")

        assert event.status == "processing"
        assert event.processing_started_at is not None


def test_recover_stuck_event_returns_it_to_received(worker_db):
    old_time = datetime.now(timezone.utc) - timedelta(minutes=2)

    with worker_db() as db:
        create_event(
            db,
            status="processing",
            processing_started_at=old_time,
        )

    worker.recover_stuck_events()

    with worker_db() as db:
        event = db.get(models.Event, "worker-test-event")

        assert event.status == "received"
        assert event.retry_count == 1
        assert event.last_error == "Worker timed out during processing"
        assert event.processing_started_at is None
        assert event.next_retry_at is None


def test_recover_stuck_event_marks_failed_at_retry_limit(worker_db):
    old_time = datetime.now(timezone.utc) - timedelta(minutes=2)

    with worker_db() as db:
        create_event(
            db,
            status="processing",
            retry_count=2,
            processing_started_at=old_time,
        )

    worker.recover_stuck_events()

    with worker_db() as db:
        event = db.get(models.Event, "worker-test-event")

        assert event.status == "failed"
        assert event.retry_count == worker.MAX_RETRIES
        assert event.processing_started_at is None


def test_process_event_completes_successfully():
    event = {
        "id": "success-event",
        "event_type": "order.created",
        "source": "pytest",
        "payload": {},
    }

    worker.process_event(event)


def test_process_event_raises_simulated_failure():
    event = {
        "id": "failure-event",
        "event_type": "order.created",
        "source": "pytest",
        "payload": {"simulate_failure": True},
    }

    with pytest.raises(RuntimeError, match="Simulated processing failure"):
        worker.process_event(event)


def test_mark_event_processed_updates_database(worker_db):
    with worker_db() as db:
        create_event(
            db,
            status="processing",
            processing_started_at=datetime.now(timezone.utc),
        )

    worker.mark_event_processed("worker-test-event")

    with worker_db() as db:
        event = db.get(models.Event, "worker-test-event")

        assert event.status == "processed"
        assert event.last_error is None
        assert event.next_retry_at is None
        assert event.processing_started_at is None


def test_mark_missing_event_processed_does_not_crash(worker_db):
    worker.mark_event_processed("missing-event")



def test_handle_event_failure_schedules_first_retry(worker_db):
    with worker_db() as db:
        create_event(
            db,
            status="processing",
            processing_started_at=datetime.now(timezone.utc),
        )

    before = datetime.now(timezone.utc)

    worker.handle_event_failure(
        "worker-test-event",
        RuntimeError("Temporary failure"),
    )

    after = datetime.now(timezone.utc)

    with worker_db() as db:
        event = db.get(models.Event, "worker-test-event")

        assert event.status == "received"
        assert event.retry_count == 1
        assert event.last_error == "Temporary failure"
        assert event.next_retry_at is not None
        assert event.processing_started_at is None

        retry_time = event.next_retry_at

        # SQLite returns naive datetimes for timezone columns.
        if retry_time.tzinfo is None:
            retry_time = retry_time.replace(tzinfo=timezone.utc)

        delay = (retry_time - before).total_seconds()

        assert 0 < delay <= 5.5
        assert retry_time <= after + timedelta(seconds=5.5)



def test_handle_event_failure_marks_failed_at_retry_limit(worker_db):
    with worker_db() as db:
        create_event(
            db,
            status="processing",
            retry_count=2,
        )

    worker.handle_event_failure(
        "worker-test-event",
        RuntimeError("Permanent failure"),
    )

    with worker_db() as db:
        event = db.get(models.Event, "worker-test-event")

        assert event.status == "failed"
        assert event.retry_count == 3
        assert event.last_error == "Permanent failure"
        assert event.next_retry_at is None


def test_handle_missing_event_failure_does_not_crash(worker_db):
    worker.handle_event_failure(
        "missing-event",
        RuntimeError("Missing event"),
    )


def test_run_worker_sleeps_when_no_event(monkeypatch):
    calls = {"count": 0}

    def stop_worker():
        calls["count"] += 1
        if calls["count"] == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(worker, "recover_stuck_events", lambda: None)
    monkeypatch.setattr(worker, "claim_event", lambda: None)
    monkeypatch.setattr(worker.time, "sleep", lambda _: stop_worker())

    with pytest.raises(KeyboardInterrupt):
        worker.run_worker()

    assert calls["count"] == 2


def test_run_worker_processes_event(monkeypatch):
    event = {"id": "worker-test-event"}
    calls = []

    monkeypatch.setattr(worker, "recover_stuck_events", lambda: None)
    monkeypatch.setattr(worker, "claim_event", lambda: event)
    monkeypatch.setattr(
        worker,
        "process_event",
        lambda claimed_event: calls.append(("process", claimed_event["id"])),
    )
    monkeypatch.setattr(
        worker,
        "mark_event_processed",
        lambda event_id: calls.append(("processed", event_id)),
    )

    def stop_worker():
        raise KeyboardInterrupt

    monkeypatch.setattr(worker, "claim_event", lambda: event if not calls else None)
    monkeypatch.setattr(worker.time, "sleep", lambda _: stop_worker())

    with pytest.raises(KeyboardInterrupt):
        worker.run_worker()

    assert calls == [
        ("process", "worker-test-event"),
        ("processed", "worker-test-event"),
    ]


def test_run_worker_handles_processing_exception(monkeypatch):
    event = {"id": "worker-test-event"}
    calls = []

    monkeypatch.setattr(worker, "recover_stuck_events", lambda: None)
    monkeypatch.setattr(worker, "claim_event", lambda: event)
    monkeypatch.setattr(
        worker,
        "process_event",
        lambda _: (_ for _ in ()).throw(RuntimeError("Processing failed")),
    )
    monkeypatch.setattr(
        worker,
        "handle_event_failure",
        lambda event_id, error: calls.append((event_id, str(error))),
    )

    def stop_worker():
        raise KeyboardInterrupt

    monkeypatch.setattr(worker, "claim_event", lambda: event if not calls else None)
    monkeypatch.setattr(worker.time, "sleep", lambda _: stop_worker())

    with pytest.raises(KeyboardInterrupt):
        worker.run_worker()

    assert calls == [("worker-test-event", "Processing failed")]


def test_main_entry_point_handles_keyboard_interrupt(monkeypatch):
    logged_messages = []

    monkeypatch.setattr(
        worker,
        "run_worker",
        lambda: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    monkeypatch.setattr(
        worker.logger,
        "info",
        lambda *args: logged_messages.append(args),
    )

    worker.main()

    assert logged_messages[-1] == ("RelayOps worker stopped.",)