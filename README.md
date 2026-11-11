# RelayOps

RelayOps is an event processing platform built with Python, FastAPI, PostgreSQL, and Docker.

It provides an API for receiving events, a background worker for processing them, automatic retries for failed events, and a dashboard for monitoring event activity.

## Features

- REST API for creating and retrieving events
- PostgreSQL database persistence
- Background event processing
- Automatic retry handling
- Configurable retry limits
- Recovery of events stuck in processing
- Event status tracking
- Search and status filtering
- Dashboard with event statistics
- Event details and manual retry controls
- Pagination and automatic dashboard refresh
- Docker Compose environment
- Nginx reverse proxy
- Automated backend tests

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Frontend | HTML, CSS, JavaScript |
| Web server | Nginx |
| Background processing | Python worker |
| Containers | Docker, Docker Compose |
| Testing | Pytest |

## Architecture

RelayOps uses four main services:

1. Frontend: Displays event activity and communicates with the API.
2. API: Accepts requests, validates data, and manages events.
3. Worker: Processes pending events and handles retries.
4. Database: Stores event records and processing information.

## Getting Started

### Requirements

- Docker Desktop
- Git

### Run with Docker Compose

Clone the repository:

```bash
git clone YOUR_REPOSITORY_URL
cd relayops
```

Create a root `.env` file using `.env.example` as a reference.

Fill in your local PostgreSQL credentials.

Start the application:

```bash
docker compose up --build -d
```

Open the dashboard:

http://localhost:5500

API documentation:

http://localhost:8000/docs

Check container status:

```bash
docker compose ps
```

Stop the application:

```bash
docker compose down
```

Your database volume remains intact when you stop the application this way.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API health check |
| GET | `/events` | Retrieve events |
| POST | `/events` | Create an event |
| GET | `/events/stats` | Retrieve event statistics |
| GET | `/events/{event_id}` | Retrieve one event |
| POST | `/events/{event_id}/retry` | Retry a failed event |
| PATCH | `/events/{event_id}/status` | Update event status |

## Event Lifecycle

Events follow these statuses:

- `received`: Event accepted by the API.
- `processing`: Worker is processing the event.
- `processed`: Event completed successfully.
- `failed`: Event exhausted its retry attempts.

## Testing

The backend test suite uses Pytest.

Run tests from the backend directory:

```bash
python -m pytest -v
```

Current test status: 24 passing tests.

## Project Structure

```text
relayops/
├── backend/
│   ├── tests/
│   ├── main.py
│   ├── worker.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── logging_config.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
└── README.md
```

## Security

- Environment files containing credentials are excluded from Git.
- The backend container runs as a non-root user.
- PostgreSQL is not exposed through a public host port in the development Compose configuration.
- Nginx routes frontend API requests to the backend service.

## Project Status

The application currently runs through Docker Compose. The backend test suite passes all 24 tests, and the main event processing workflow has been verified.

Production deployment preparation remains in progress.