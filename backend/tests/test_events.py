from fastapi.testclient import TestClient

from main import app


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
