from .types import LLMTool


OPEN_TICKET_TOOL = LLMTool(
    name="openTicket",
    description=(
        "Create a new customer support ticket when the user wants to create, open, "
        "file, report, or add an issue for support. Use this only when the user "
        "provides a customer email address and describes the issue to add to the "
        "ticket. Returns false if the customer email is not found; otherwise returns "
        "success true and the created ticketId."
    ),
    parameters={
        "type": "object",
        "properties": {
            "customerEmail": {
                "type": "string",
                "format": "email",
                "description": "The email address of the customer who needs a ticket.",
            },
            "issue": {
                "type": "string",
                "description": "The customer issue or support request to add to the ticket.",
            },
        },
        "required": ["customerEmail", "issue"],
        "additionalProperties": False,
    },
)


ORDER_STATUS_TOOL = LLMTool(
    name="OrderStatus",
    description=(
        "Look up a customer's orders and their current statuses when the user asks "
        "about order status, order tracking, where an order is, recent orders, or "
        "which orders are associated with an email address. Use this only when the "
        "user provides a customer email address. Returns 'No customer found' if the "
        "email does not match a customer, 'No order found' if the customer has no "
        "orders, otherwise returns an orders list with orderId and status values "
        "ordered most recent first."
    ),
    parameters={
        "type": "object",
        "properties": {
            "Email": {
                "type": "string",
                "format": "email",
                "description": "The email address of the customer whose orders should be checked.",
            },
        },
        "required": ["Email"],
        "additionalProperties": False,
    },
)


CUSTOMER_SUPPORT_TOOLS = [OPEN_TICKET_TOOL, ORDER_STATUS_TOOL]
