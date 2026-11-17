from fastapi.testclient import TestClient

from main import app
import asyncio
import main
from starlette.requests import Request


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_event():
    response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {
                "order_id": 9001
            }
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["event_type"] == "order.created"
    assert data["source"] == "pytest"
    assert data["payload"]["order_id"] == 9001
    assert data["status"] == "received"
    assert "id" in data

def test_get_event():
    create_response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {
                "order_id": 9002
            }
        }
    )

    event_id = create_response.json()["id"]

    response = client.get(f"/events/{event_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == event_id
    assert data["event_type"] == "order.created"
    assert data["payload"]["order_id"] == 9002

def test_list_events():
    response = client.get("/events")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

def test_update_event_status():
    create_response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {
                "order_id": 9003
            }
        }
    )

    event_id = create_response.json()["id"]

    processing_response = client.patch(
        f"/events/{event_id}/status",
        json={
            "status": "processing"
        }
    )

    assert processing_response.status_code == 200
    assert processing_response.json()["status"] == "processing"

    processed_response = client.patch(
        f"/events/{event_id}/status",
        json={
            "status": "processed"
        }
    )

    assert processed_response.status_code == 200
    assert processed_response.json()["status"] == "processed"

def test_retry_failed_event():
    create_response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {
                "order_id": 9004
            }
        }
    )

    event_id = create_response.json()["id"]

    failed_response = client.patch(
        f"/events/{event_id}/status",
        json={
            "status": "processing"
        }
    )

    assert failed_response.status_code == 200

    failed_response = client.patch(
        f"/events/{event_id}/status",
        json={
            "status": "failed"
        }
    )

    assert failed_response.status_code == 200

    retry_response = client.post(
        f"/events/{event_id}/retry"
    )

    assert retry_response.status_code == 200

    data = retry_response.json()

    assert data["status"] == "received"
    assert data["retry_count"] == 0
    assert data["last_error"] is None
    assert data["next_retry_at"] is None

def test_retry_non_failed_event():
    create_response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {
                "order_id": 9005
            }
        }
    )

    event_id = create_response.json()["id"]

    response = client.post(
        f"/events/{event_id}/retry"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only failed events can be retried"

def test_missing_event():
    event_id = "00000000-0000-0000-0000-000000000000"

    get_response = client.get(f"/events/{event_id}")

    assert get_response.status_code == 404

    retry_response = client.post(
        f"/events/{event_id}/retry"
    )

    assert retry_response.status_code == 404



def test_event_stats():
    client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {"order_id": 1001},
        },
    )

    response = client.get("/events/stats")

    assert response.status_code == 200
    stats = response.json()
    assert isinstance(stats, dict)


def test_invalid_event_creation():
    response = client.post(
        "/events",
        json={
            "event_type": "",
            "source": "pytest",
            "payload": {"order_id": 1001},
        },
    )

    assert response.status_code == 422


def test_event_list_status_filter():
    response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {"order_id": 1002},
        },
    )

    assert response.status_code == 201

    response = client.get("/events?status=received")

    assert response.status_code == 200

    events = response.json()
    assert all(event["status"] == "received" for event in events)


def test_event_not_found():
    response = client.get(
        "/events/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


def test_event_pagination_limit():
    response = client.get("/events?limit=2")

    assert response.status_code == 200
    assert len(response.json()) <= 2


def test_event_pagination_skip():
    first_page = client.get("/events?skip=0&limit=1")
    second_page = client.get("/events?skip=1&limit=1")

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    if first_page.json() and second_page.json():
        assert first_page.json()[0]["id"] != second_page.json()[0]["id"]


def test_event_pagination_invalid_limit():
    response = client.get("/events?limit=101")

    assert response.status_code == 400


def test_event_pagination_negative_skip():
    response = client.get("/events?skip=-1")

    assert response.status_code == 400


def test_create_event_rejects_whitespace_event_type():
    response = client.post(
        "/events",
        json={
            "event_type": "   ",
            "source": "pytest",
            "payload": {"order_id": 2001},
        },
    )

    assert response.status_code == 422


def test_create_event_rejects_whitespace_source():
    response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "   ",
            "payload": {"order_id": 2002},
        },
    )

    assert response.status_code == 422


def test_create_event_rejects_array_payload():
    response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": [1, 2, 3],
        },
    )

    assert response.status_code == 422


def test_create_event_strips_whitespace():
    response = client.post(
        "/events",
        json={
            "event_type": "  order.created  ",
            "source": "  pytest  ",
            "payload": {"order_id": 2003},
        },
    )

    assert response.status_code == 201
    assert response.json()["event_type"] == "order.created"
    assert response.json()["source"] == "pytest"


def test_create_event_response_includes_processing_started_at():
    response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {"order_id": 2004},
        },
    )

    assert response.status_code == 201
    assert "processing_started_at" in response.json()
    assert response.json()["processing_started_at"] is None


def test_event_list_rejects_invalid_status():
    response = client.get("/events?status=unknown")

    assert response.status_code == 400


def test_event_pagination_rejects_zero_limit():
    response = client.get("/events?limit=0")

    assert response.status_code == 400


def test_event_status_rejects_unknown_value():
    create_response = client.post(
        "/events",
        json={
            "event_type": "order.created",
            "source": "pytest",
            "payload": {"order_id": 2005},
        },
    )

    event_id = create_response.json()["id"]

    response = client.patch(
        f"/events/{event_id}/status",
        json={"status": "unknown"},
    )

    assert response.status_code == 422


def test_api_lifespan_startup_and_shutdown(monkeypatch):
    create_calls = []
    log_messages = []

    def mock_create_all(*, bind):
        create_calls.append(bind)

    monkeypatch.setattr(
        main.Base.metadata,
        "create_all",
        mock_create_all,
    )
    monkeypatch.setattr(
        main.logger,
        "info",
        lambda *args: log_messages.append(args),
    )

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan())

    assert create_calls == [main.engine]
    assert len(log_messages) == 2
    assert log_messages[0][0] == (
        "RelayOps API started. Database tables verified."
    )
    assert log_messages[1][0] == "RelayOps API shutting down."


def test_unexpected_error_handler_returns_500(monkeypatch):
    log_messages = []

    monkeypatch.setattr(
        main.logger,
        "exception",
        lambda *args: log_messages.append(args),
    )

    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
    })

    response = asyncio.run(
        main.unexpected_error_handler(
            request,
            RuntimeError("Test exception"),
        )
    )

    assert response.status_code == 500
    assert response.body == b'{"detail":"Internal server error"}'
    assert len(log_messages) == 1


def test_update_status_event_not_found():
    response = client.patch(
        "/events/nonexistent-event/status",
        json={"status": "processing"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"


def test_update_status_rejects_invalid_transition():
    create_response = client.post(
        "/events",
        json={
            "event_type": "test.event",
            "source": "pytest",
            "payload": {}
        }
    )

    assert create_response.status_code == 201

    event_id = create_response.json()["id"]

    response = client.patch(
        f"/events/{event_id}/status",
        json={"status": "processed"}
    )

    assert response.status_code == 400
    assert "Cannot transition from received to processed" in response.json()["detail"]

def test_strip_required_strings_preserves_non_string_values():
    from schemas import EventCreate

    result = EventCreate.strip_required_strings(123)

    assert result == 123