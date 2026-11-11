const API_URL = "/api";

const elements = {
    total: document.getElementById("total-count"),
    received: document.getElementById("received-count"),
    processing: document.getElementById("processing-count"),
    processed: document.getElementById("processed-count"),
    failed: document.getElementById("failed-count"),
    connection: document.getElementById("connection-status"),
    lastUpdated: document.getElementById("last-updated"),
    error: document.getElementById("error-message"),
    refresh: document.getElementById("refresh-button"),

    eventCount: document.getElementById("event-count"),
    eventsBody: document.getElementById("events-table-body"),
    eventsError: document.getElementById("events-error"),
    search: document.getElementById("event-search"),
    statusFilter: document.getElementById("status-filter"),
    modal: document.getElementById("event-modal"),
    eventDetails: document.getElementById("event-details"),
    closeModal: document.getElementById("close-modal"),
    eventActions: document.getElementById("event-actions"),
    previousPage: document.getElementById("previous-page"),
    nextPage: document.getElementById("next-page"),
    pageNumber: document.getElementById("page-number"),
    createModal: document.getElementById("create-event-modal"),
    addEventButton: document.getElementById("add-event-button"),
    closeCreateModal: document.getElementById("close-create-modal"),
    createEventForm: document.getElementById("create-event-form"),
    eventType: document.getElementById("event-type"),
    eventSource: document.getElementById("event-source"),
    eventPayload: document.getElementById("event-payload"),
    createEventError: document.getElementById("create-event-error"),
    submitEventButton: document.getElementById("submit-event-button"),
    cancelCreateEvent: document.getElementById("cancel-create-event"),
};

let allEvents = [];
let currentPage = 0;
const EVENTS_PER_PAGE = 10;

async function loadStats() {
    elements.error.textContent = "";

    try {
        const response = await fetch(`${API_URL}/events/stats`);

        if (!response.ok) {
            throw new Error(`API returned status ${response.status}`);
        }

        const stats = await response.json();

        elements.total.textContent = stats.total;
        elements.received.textContent = stats.received;
        elements.processing.textContent = stats.processing;
        elements.processed.textContent = stats.processed;
        elements.failed.textContent = stats.failed;

        elements.connection.textContent = "Connected";
        elements.lastUpdated.textContent =
            `Updated at ${new Date().toLocaleTimeString()}`;

    } catch (error) {
        elements.connection.textContent = "Disconnected";
        elements.error.textContent =
            `Unable to load statistics: ${error.message}`;
    }
}


function renderEvents() {
    const searchTerm = elements.search.value.trim().toLowerCase();
    const selectedStatus = elements.statusFilter.value;

    const filteredEvents = allEvents.filter(event => {
        const matchesSearch =
            event.id.toLowerCase().includes(searchTerm) ||
            event.event_type.toLowerCase().includes(searchTerm);

        const matchesStatus =
            selectedStatus === "all" ||
            event.status === selectedStatus;

        return matchesSearch && matchesStatus;
    });

    const totalPages = Math.max(
        1,
        Math.ceil(filteredEvents.length / EVENTS_PER_PAGE)
    );

    currentPage = Math.min(currentPage, totalPages - 1);

    const start = currentPage * EVENTS_PER_PAGE;
    const paginatedEvents = filteredEvents.slice(
        start,
        start + EVENTS_PER_PAGE
    );

    elements.eventCount.textContent =
        `${filteredEvents.length} of ${allEvents.length} events`;

    if (filteredEvents.length === 0) {
        elements.eventsBody.innerHTML = `
            <tr>
                <td colspan="6">No matching events found.</td>
            </tr>
        `;
    } else {
        elements.eventsBody.innerHTML = paginatedEvents.map(event => `
            <tr class="event-row" data-event-id="${event.id}">
                <td class="event-id">${event.id}</td>
                <td>${event.event_type}</td>
                <td>${event.source}</td>
                <td>
                    <span class="status-badge status-${event.status}">
                        ${event.status}
                    </span>
                </td>
                <td>${event.retry_count}</td>
                <td>${new Date(event.created_at).toLocaleString()}</td>
            </tr>
        `).join("");

        elements.eventsBody.querySelectorAll(".event-row").forEach(row => {
            row.addEventListener("click", () => {
                loadEventDetails(row.dataset.eventId);
            });
        });
    }

    elements.previousPage.disabled = currentPage === 0;
    elements.nextPage.disabled = currentPage >= totalPages - 1;
    elements.pageNumber.textContent =
        `Page ${currentPage + 1} of ${totalPages}`;
}


async function loadEvents() {
    try {
        elements.eventsError.textContent = "";

        const response = await fetch(`${API_URL}/events?limit=100`);

        if (!response.ok) {
            throw new Error(`API returned status ${response.status}`);
        }

        allEvents = await response.json();

        renderEvents();

    } catch (error) {
        console.error("Error loading events:", error);

        elements.eventsBody.innerHTML = `
            <tr>
                <td colspan="6">Failed to load events.</td>
            </tr>
        `;

        elements.eventsError.textContent = error.message;
    }
}






async function loadEventDetails(eventId) {
    elements.modal.classList.add("open");
    elements.eventDetails.textContent = "Loading event details...";

    try {
        const response = await fetch(
            `${API_URL}/events/${encodeURIComponent(eventId)}`
        );

        if (!response.ok) {
            throw new Error(`API returned status ${response.status}`);
        }

        const event = await response.json();

        elements.eventActions.innerHTML = "";

        if (event.status === "failed") {
            const retryButton = document.createElement("button");

            retryButton.textContent = "Retry event";
            retryButton.className = "retry-button";

            retryButton.addEventListener("click", () => {
                retryEvent(event.id, retryButton);
            });

            elements.eventActions.appendChild(retryButton);
        }

        elements.eventDetails.innerHTML = `
            <div class="event-detail">
                <h3>Event ID</h3>
                <p>${event.id}</p>
            </div>

            <div class="event-detail">
                <h3>Event type</h3>
                <p>${event.event_type}</p>
            </div>

            <div class="event-detail">
                <h3>Source</h3>
                <p>${event.source}</p>
            </div>

            <div class="event-detail">
                <h3>Status</h3>
                <p>${event.status}</p>
            </div>

            <div class="event-detail">
                <h3>Retry count</h3>
                <p>${event.retry_count}</p>
            </div>

            <div class="event-detail">
                <h3>Created at</h3>
                <p>${new Date(event.created_at).toLocaleString()}</p>
            </div>

            <div class="event-detail">
                <h3>Last error</h3>
                <p>${event.last_error || "No errors recorded"}</p>
            </div>

            <div class="event-detail">
                <h3>Processing started</h3>
                <p>${event.processing_started_at
                    ? new Date(event.processing_started_at).toLocaleString()
                    : "Not currently processing"}</p>
            </div>

            <div class="event-detail">
                <h3>Next retry</h3>
                <p>${event.next_retry_at
                    ? new Date(event.next_retry_at).toLocaleString()
                    : "No retry scheduled"}</p>
            </div>

            <div class="event-detail">
                <h3>Payload</h3>
                <pre class="event-payload">${JSON.stringify(event.payload, null, 2)}</pre>
            </div>
        `;

    } catch (error) {
        elements.eventDetails.textContent =
            `Unable to load event details: ${error.message}`;
    }
}

async function retryEvent(eventId, button) {
    button.disabled = true;
    button.textContent = "Retrying...";

    try {
        const response = await fetch(
            `${API_URL}/events/${encodeURIComponent(eventId)}/retry`,
            {
                method: "POST",
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Retry failed");
        }

        await refreshDashboard();
        await loadEventDetails(eventId);

    } catch (error) {
        button.disabled = false;
        button.textContent = "Retry event";

        elements.eventActions.textContent =
            `Unable to retry event: ${error.message}`;
    }
}

async function refreshDashboard() {
    await Promise.all([
        loadStats(),
        loadEvents(),
    ]);
}

function openCreateEventModal() {
    elements.createEventError.textContent = "";
    elements.createModal.classList.add("open");
    elements.eventType.focus();
}

function closeCreateEventModal() {
    elements.createModal.classList.remove("open");
    elements.createEventError.textContent = "";
}

async function createEvent(event) {
    event.preventDefault();

    elements.createEventError.textContent = "";
    elements.submitEventButton.disabled = true;
    elements.submitEventButton.textContent = "Creating...";

    try {
        const eventType = elements.eventType.value.trim();
        const source = elements.eventSource.value.trim();

        let payload;

        try {
            payload = JSON.parse(elements.eventPayload.value);
        } catch {
            throw new Error("Payload must contain valid JSON.");
        }

        if (
            payload === null ||
            typeof payload !== "object" ||
            Array.isArray(payload)
        ) {
            throw new Error("Payload must be a JSON object.");
        }

        const response = await fetch(`${API_URL}/events`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                event_type: eventType,
                source: source,
                payload: payload,
            }),
        });

        const result = await response.json();

        if (!response.ok) {
            const detail = result.detail;

            throw new Error(
                typeof detail === "string"
                    ? detail
                    : JSON.stringify(detail || "Unable to create event.")
            );
        }

        elements.createEventForm.reset();

        closeCreateEventModal();

        elements.search.value = "";
        elements.statusFilter.value = "all";
        currentPage = 0;

        await refreshDashboard();

        elements.eventsError.textContent = "Event created successfully.";

    } catch (error) {
        elements.createEventError.textContent = error.message;

    } finally {
        elements.submitEventButton.disabled = false;
        elements.submitEventButton.textContent = "Create Event";
    }
}

elements.closeModal.addEventListener("click", () => {
    elements.modal.classList.remove("open");
});

elements.modal.addEventListener("click", event => {
    if (event.target === elements.modal) {
        elements.modal.classList.remove("open");
    }
});


elements.previousPage.addEventListener("click", () => {
    if (currentPage > 0) {
        currentPage--;
        renderEvents();
    }
});

elements.nextPage.addEventListener("click", () => {
    currentPage++;
    renderEvents();
});

elements.refresh.addEventListener("click", refreshDashboard);

elements.search.addEventListener("input", () => {
    currentPage = 0;
    renderEvents();
});

elements.statusFilter.addEventListener("change", () => {
    currentPage = 0;
    renderEvents();
});

elements.addEventButton.addEventListener(
    "click",
    openCreateEventModal
);

elements.closeCreateModal.addEventListener(
    "click",
    closeCreateEventModal
);

elements.cancelCreateEvent.addEventListener(
    "click",
    closeCreateEventModal
);

elements.createEventForm.addEventListener(
    "submit",
    createEvent
);

elements.createModal.addEventListener("click", event => {
    if (event.target === elements.createModal) {
        closeCreateEventModal();
    }
});

refreshDashboard();

setInterval(refreshDashboard, 5000);
