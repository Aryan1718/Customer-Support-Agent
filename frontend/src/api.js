const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export async function getHealth() {
  const [api, db, llm] = await Promise.allSettled([
    fetchJson("/health"),
    fetchJson("/health/db"),
    fetchJson("/health/llm"),
  ]);

  return {
    api: normalizeHealth(api),
    db: normalizeHealth(db),
    llm: normalizeHealth(llm),
  };
}

export async function createSession() {
  return fetchJson("/sessions", { method: "POST" });
}

export async function streamChat({
  message,
  sessionId,
  history,
  signal,
  onEvent,
}) {
  const response = await fetch(`${API_BASE_URL}/llm/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      message,
      session_id: sessionId || null,
      history,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const parsed = parseSseEvent(rawEvent);
      if (parsed) {
        onEvent(parsed);
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer);
    if (parsed) {
      onEvent(parsed);
    }
  }
}

async function fetchJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json();
}

function normalizeHealth(result) {
  if (result.status !== "fulfilled") {
    return {
      status: "unhealthy",
      detail: result.reason?.message || "Unable to reach service",
    };
  }

  return result.value;
}

function parseSseEvent(rawEvent) {
  const lines = rawEvent.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));

  if (!eventLine || dataLines.length === 0) {
    return null;
  }

  const event = eventLine.replace("event:", "").trim();
  const dataText = dataLines
    .map((line) => line.replace("data:", "").trimStart())
    .join("\n");

  try {
    return {
      event,
      data: JSON.parse(dataText),
    };
  } catch {
    return {
      event,
      data: dataText,
    };
  }
}
