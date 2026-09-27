from .types import LLMTool


CUSTOMER_INFORMATION_TOOL = LLMTool(
    name="customerInformation",
    description=(
        "Look up customer account information when the user provides a customer "
        "email address and asks about their account, profile, customer details, "
        "or identifying customer information. Returns 'No customer found' if the "
        "email does not match a customer; otherwise returns the customer id, email, "
        "name, and createdAt timestamp."
    ),
    parameters={
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "format": "email",
                "description": "The email address of the customer to look up.",
            },
        },
        "required": ["email"],
        "additionalProperties": False,
    },
)


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


UPDATE_ORDER_TOOL = LLMTool(
    name="updateOrder",
    description=(
        "Update a customer's order after verifying the customer email and order ID. "
        "Use this when the user asks to update an existing order and provides both "
        "their customer email address and order ID. Returns 'No customer found' if "
        "the email does not match a customer, 'No order found' if the order ID does "
        "not exist for that customer, 'Can not update' if the recalculated order "
        "amount differs from the current amount, otherwise returns true."
    ),
    parameters={
        "type": "object",
        "properties": {
            "Email": {
                "type": "string",
                "format": "email",
                "description": "The email address of the customer whose order should be updated.",
            },
            "OrderId": {
                "type": "integer",
                "description": "The ID of the order to update.",
            },
        },
        "required": ["Email", "OrderId"],
        "additionalProperties": False,
    },
)


REFUND_TOOL = LLMTool(
    name="Refund",
    description=(
        "Evaluate whether a customer's order refund can be approved automatically "
        "or needs human approval. Use this when the user asks to refund an order "
        "and provides both their customer email address and order ID. Returns 'No "
        "customer found' if the email does not match a customer, 'No order exists' "
        "if the order ID does not exist for that customer, true when the calculated "
        "refund amount is less than $10, otherwise returns 'Human Approval'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "format": "email",
                "description": "The email address of the customer requesting a refund.",
            },
            "orderID": {
                "type": "integer",
                "description": "The ID of the order the customer wants refunded.",
            },
        },
        "required": ["email", "orderID"],
        "additionalProperties": False,
    },
)


CUSTOMER_SUPPORT_TOOLS = [
    CUSTOMER_INFORMATION_TOOL,
    OPEN_TICKET_TOOL,
    ORDER_STATUS_TOOL,
    UPDATE_ORDER_TOOL,
    REFUND_TOOL,
]
