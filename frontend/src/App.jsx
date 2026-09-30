import { useEffect, useMemo, useRef, useState } from "react";
import { createSession, getHealth, streamChat } from "./api";

const SESSION_STORAGE_KEY = "customer-support-agent-session-id";

const INITIAL_MESSAGES = [
  {
    id: "welcome",
    role: "assistant",
    content:
      "I am ready to help with customer lookup, order status, refunds, order updates, and support tickets.",
    timestamp: new Date().toISOString(),
  },
];

const STAGE_LABELS = {
  received: "Request received",
  loading_session: "Loading session",
  calling_llm: "Calling model",
  planning: "Planning support action",
  collecting_missing_information: "Collecting missing information",
  executing_tool: "Executing backend tool",
  generating_tool_response: "Writing grounded response",
  validating_response: "Validating response",
  finalizing: "Finalizing answer",
  storing_conversation: "Saving conversation",
};

function App() {
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState(
    () => localStorage.getItem(SESSION_STORAGE_KEY) || "",
  );
  const [health, setHealth] = useState(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeStage, setActiveStage] = useState("Idle");
  const [stageHistory, setStageHistory] = useState([]);
  const [backendAction, setBackendAction] = useState(null);
  const [model, setModel] = useState("");
  const [error, setError] = useState("");
  const abortControllerRef = useRef(null);
  const transcriptRef = useRef(null);

  const canSend = draft.trim().length > 0 && !isStreaming;

  const healthSummary = useMemo(() => {
    if (!health) {
      return "Not checked";
    }

    const unhealthy = Object.values(health).filter(
      (item) => item.status !== "healthy",
    );

    return unhealthy.length === 0 ? "All systems healthy" : "Attention needed";
  }, [health]);

  useEffect(() => {
    refreshHealth();
  }, []);

  useEffect(() => {
    transcriptRef.current?.scrollTo({
      top: transcriptRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, activeStage]);

  async function refreshHealth() {
    setIsCheckingHealth(true);
    try {
      setHealth(await getHealth());
    } catch (err) {
      setError(err.message || "Unable to check backend health.");
    } finally {
      setIsCheckingHealth(false);
    }
  }

  async function startNewSession() {
    setError("");
    setBackendAction(null);
    setStageHistory([]);
    setActiveStage("Creating session");

    try {
      const session = await createSession();
      setSessionId(session.session_id);
      localStorage.setItem(SESSION_STORAGE_KEY, session.session_id);
      setMessages([
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "New support session started. What can I help with?",
          timestamp: new Date().toISOString(),
        },
      ]);
      setActiveStage("Idle");
    } catch (err) {
      setActiveStage("Idle");
      setError(err.message || "Unable to create a new session.");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const userText = draft.trim();
    if (!userText || isStreaming) {
      return;
    }

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: userText,
      timestamp: new Date().toISOString(),
    };
    const assistantMessageId = crypto.randomUUID();

    setDraft("");
    setError("");
    setBackendAction(null);
    setStageHistory([]);
    setActiveStage("Starting request");
    setMessages((current) => [
      ...current,
      userMessage,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        streaming: true,
      },
    ]);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    setIsStreaming(true);

    try {
      await streamChat({
        message: userText,
        sessionId,
        history: buildRequestHistory(messages),
        signal: abortController.signal,
        onEvent: ({ event: eventName, data }) => {
          if (eventName === "status") {
            handleStatusEvent(data);
          }

          if (eventName === "metadata") {
            handleMetadataEvent(data);
          }

          if (eventName === "content") {
            appendAssistantDelta(assistantMessageId, data.delta || "");
          }

          if (eventName === "done") {
            handleDoneEvent(assistantMessageId, data);
          }
        },
      });
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err.message || "The chat stream failed.");
        markAssistantError(assistantMessageId);
      }
    } finally {
      abortControllerRef.current = null;
      setIsStreaming(false);
      setActiveStage("Idle");
    }
  }

  function handleStatusEvent(data) {
    const label = STAGE_LABELS[data.stage] || data.stage || "Working";
    setActiveStage(label);
    setStageHistory((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        label,
        detail: data.detail || null,
      },
    ]);

    if (data.stage === "executing_tool" && data.detail?.tool_name) {
      setBackendAction({
        toolName: data.detail.tool_name,
        params: data.detail.tool_params || {},
      });
    }
  }

  function handleMetadataEvent(data) {
    if (data.session_id) {
      setSessionId(data.session_id);
      localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
    }

    if (data.model) {
      setModel(data.model);
    }
  }

  function handleDoneEvent(messageId, data) {
    handleMetadataEvent(data);
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content: data.content || message.content,
              streaming: false,
              timestamp: new Date().toISOString(),
            }
          : message,
      ),
    );
  }

  function appendAssistantDelta(messageId, delta) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId
          ? { ...message, content: `${message.content}${delta}` }
          : message,
      ),
    );
  }

  function markAssistantError(messageId) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content:
                message.content ||
                "I could not complete that request. Check the backend and try again.",
              streaming: false,
              failed: true,
            }
          : message,
      ),
    );
  }

  function stopStreaming() {
    abortControllerRef.current?.abort();
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Support console controls">
        <section className="brand-panel">
          <div>
            <p className="eyebrow">Support Operations</p>
            <h1>Customer Support Agent</h1>
          </div>
          <span className="version-pill">Console</span>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Session</h2>
              <p>{sessionId ? "Active browser session" : "No session yet"}</p>
            </div>
            <button className="icon-button" onClick={startNewSession} type="button">
              New
            </button>
          </div>
          <dl className="metadata-list">
            <div>
              <dt>Session ID</dt>
              <dd title={sessionId || "Not assigned"}>
                {sessionId ? compactId(sessionId) : "Auto-created on send"}
              </dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{model || health?.llm?.model || "Pending"}</dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Backend Health</h2>
              <p>{healthSummary}</p>
            </div>
            <button
              className="icon-button"
              disabled={isCheckingHealth}
              onClick={refreshHealth}
              type="button"
            >
              Check
            </button>
          </div>
          <div className="health-grid">
            <HealthItem label="API" value={health?.api} />
            <HealthItem label="DB" value={health?.db} />
            <HealthItem label="LLM" value={health?.llm} />
          </div>
        </section>

        <section className="panel panel-fill">
          <div className="panel-header">
            <div>
              <h2>Backend Action</h2>
              <p>{backendAction ? "Tool execution detected" : "Waiting"}</p>
            </div>
          </div>
          {backendAction ? (
            <div className="action-box">
              <strong>{backendAction.toolName}</strong>
              <pre>{JSON.stringify(backendAction.params, null, 2)}</pre>
            </div>
          ) : (
            <p className="muted-text">
              The server will choose customer, order, refund, update, or ticket
              tools when needed.
            </p>
          )}
        </section>
      </aside>

      <section className="workspace" aria-label="Customer support chat">
        <header className="topbar">
          <div>
            <p className="eyebrow">Live Agent Workflow</p>
            <h2>Conversation</h2>
          </div>
          <div className="status-cluster">
            <span className={isStreaming ? "live-dot active" : "live-dot"} />
            <span>{activeStage}</span>
          </div>
        </header>

        <div className="progress-strip" aria-live="polite">
          {stageHistory.length === 0 ? (
            <span className="muted-text">No active backend steps.</span>
          ) : (
            stageHistory.slice(-5).map((stage) => (
              <span className="stage-chip" key={stage.id}>
                {stage.label}
              </span>
            ))
          )}
        </div>

        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}

        <div className="transcript" ref={transcriptRef}>
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            aria-label="Message"
            disabled={isStreaming}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Ask about an order, refund, account, update, or support ticket..."
            rows={3}
            value={draft}
          />
          <div className="composer-actions">
            <span>{draft.length}/1200</span>
            {isStreaming ? (
              <button className="secondary-button" onClick={stopStreaming} type="button">
                Stop
              </button>
            ) : (
              <button className="primary-button" disabled={!canSend} type="submit">
                Send
              </button>
            )}
          </div>
        </form>
      </section>
    </main>
  );
}

function HealthItem({ label, value }) {
  const status = value?.status || "unknown";

  return (
    <div className="health-item">
      <span className={`health-dot ${status}`} />
      <div>
        <strong>{label}</strong>
        <small>{status}</small>
      </div>
    </div>
  );
}

function MessageBubble({ message }) {
  return (
    <article className={`message-row ${message.role}`}>
      <div className="message-meta">
        <span>{message.role === "user" ? "You" : "Assistant"}</span>
        <time>{formatTime(message.timestamp)}</time>
      </div>
      <div className={message.failed ? "message failed" : "message"}>
        {message.content || <span className="typing-text">Thinking...</span>}
        {message.streaming && message.content ? <span className="cursor" /> : null}
      </div>
    </article>
  );
}

function buildRequestHistory(messages) {
  return messages
    .filter((message) => message.id !== "welcome")
    .filter((message) => message.content.trim())
    .slice(-8)
    .map((message) => ({
      role: message.role,
      content: message.content,
    }));
}

function compactId(value) {
  if (value.length <= 14) {
    return value;
  }

  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export default App;
