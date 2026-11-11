
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4
import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from database import Base, engine, get_db
from logging_config import configure_logging
from schemas import EventCreate, EventRead, EventStatusUpdate


configure_logging()
logger = logging.getLogger("relayops.api")

VALID_EVENT_STATUSES = {
    "received",
    "processing",
    "processed",
    "failed",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("RelayOps API started. Database tables verified.")

    yield

    logger.info("RelayOps API shutting down.")


app = FastAPI(title="RelayOps API", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unexpected_error_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unexpected API error. method=%s path=%s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/events/stats")
def get_event_stats(db: Session = Depends(get_db)):
    status_counts = (
        db.query(
            models.Event.status,
            func.count(models.Event.id),
        )
        .group_by(models.Event.status)
        .all()
    )

    counts = {
        "received": 0,
        "processing": 0,
        "processed": 0,
        "failed": 0,
    }

    for status, count in status_counts:
        counts[status] = count

    return {
        "total": sum(counts.values()),
        **counts,
    }


@app.post("/events", response_model=EventRead, status_code=201)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
):
    event = models.Event(
        id=str(uuid4()),
        event_type=event_data.event_type,
        source=event_data.source,
        payload=event_data.payload,
        status="received",
        created_at=datetime.now(timezone.utc),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    logger.info(
        "Event created. id=%s type=%s source=%s",
        event.id,
        event.event_type,
        event.source,
    )

    return event


@app.get("/events", response_model=list[EventRead])
def list_events(
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    if status is not None and status not in VALID_EVENT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Status must be one of: "
                "received, processing, processed, failed"
            ),
        )

    if skip < 0:
        raise HTTPException(
            status_code=400,
            detail="Skip cannot be negative",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    query = db.query(models.Event)

    if status is not None:
        query = query.filter(models.Event.status == status)

    return (
        query
        .order_by(models.Event.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.get("/events/{event_id}", response_model=EventRead)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id
    ).first()

    if event is None:
        logger.warning("Event lookup failed. id=%s", event_id)
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    return event


@app.post("/events/{event_id}/retry", response_model=EventRead)
def retry_event(
    event_id: str,
    db: Session = Depends(get_db),
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id
    ).first()

    if event is None:
        logger.warning(
            "Manual retry failed. Event not found. id=%s",
            event_id,
        )
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    if event.status != "failed":
        logger.warning(
            "Manual retry rejected. id=%s status=%s",
            event_id,
            event.status,
        )
        raise HTTPException(
            status_code=400,
            detail="Only failed events can be retried",
        )

    event.status = "received"
    event.retry_count = 0
    event.last_error = None
    event.next_retry_at = None
    event.processing_started_at = None

    db.commit()
    db.refresh(event)

    logger.info("Manual retry requested. id=%s", event_id)

    return event


@app.patch("/events/{event_id}/status", response_model=EventRead)
def update_event_status(
    event_id: str,
    status_data: EventStatusUpdate,
    db: Session = Depends(get_db),
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id
    ).first()

    if event is None:
        logger.warning(
            "Status update failed. Event not found. id=%s",
            event_id,
        )
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    allowed_transitions = {
        "received": ["processing"],
        "processing": ["processed", "failed"],
        "failed": ["processing"],
        "processed": [],
    }

    if status_data.status not in allowed_transitions[event.status]:
        logger.warning(
            "Invalid status transition. id=%s from=%s to=%s",
            event_id,
            event.status,
            status_data.status,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot transition from {event.status} "
                f"to {status_data.status}"
            ),
        )

    previous_status = event.status
    event.status = status_data.status

    db.commit()
    db.refresh(event)

    logger.info(
        "Event status updated. id=%s from=%s to=%s",
        event_id,
        previous_status,
        event.status,
    )

    return event
