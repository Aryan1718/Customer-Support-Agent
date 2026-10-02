# openTicket Issue Investigation

## Issue

Normal chat messages are being stored as new rows in the `ticket` table.

Recent ticket rows show messages such as:

```text
"11"
"Yes that would be much help"
```

These are not valid support ticket issue descriptions. They are ordinary chat follow-up messages, but the backend created tickets from them.

## Why It Is Happening

The backend does not store every chat response in the `ticket` table directly. A ticket is inserted only when the `openTicket` tool is executed.

The incorrect behavior happens because the tool-planning flow can turn a normal chat message into an `openTicket` tool execution.

The main causes are:

1. `openTicket` writes directly to the `ticket` table.
   The insert happens in `backend/app/tools/tickets.py` when `openTicket()` calls `open_ticket_with_session()`.

2. Session parameters are reused across turns.
   `backend/app/llm/tool_orchestrator.py` merges previous `session.collected_params` with the current message's extracted params.

3. Collected params are not cleared after a tool finishes.
   `backend/app/session_store.py` updates `collected_params` by merging new values into the old values, so an email from an earlier turn can remain available for later tool calls.

4. Any non-empty message becomes the ticket issue when the selected or active tool is `openTicket`.
   In `backend/app/llm/parameter_extraction.py`, this rule exists:

   ```python
   if tool_name == "openTicket" and user_message.strip():
       params["issue"] = user_message.strip()
   ```

   Because of this, messages like `"11"` or `"Yes that would be much help"` can become the `issue` field.

## Root Cause

The root cause is stale session state combined with overly broad ticket issue extraction.

If the session already has a customer email from a previous step, and the planner or LLM selects `openTicket`, the backend only needs an `issue` value to execute the ticket tool. Since the current user message is automatically treated as the issue, the backend can create a ticket from unrelated follow-up text.

In short:

```text
stale email in session
+ openTicket selected/active
+ any non-empty user message treated as issue
= unintended ticket row
```

## Expected Behavior

A ticket should only be created when the user clearly wants a ticket opened, and the ticket issue should be a real issue summary, not any arbitrary follow-up message.

For safer behavior, ticket creation should require explicit ticket intent or user confirmation before writing to the database.
