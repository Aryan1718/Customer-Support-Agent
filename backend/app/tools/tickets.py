from typing import Literal, TypedDict

from pydantic import BaseModel, PositiveInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_session_factory
from database.models import Customer, Ticket


class OpenTicketSuccess(BaseModel):
    success: Literal[True] = True
    ticketId: PositiveInt


class OpenTicketSuccessPayload(TypedDict):
    success: Literal[True]
    ticketId: int


OpenTicketResult = OpenTicketSuccessPayload | Literal[False]


def _dump_success(payload: OpenTicketSuccess) -> OpenTicketSuccessPayload:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()

    return payload.dict()


def open_ticket_with_session(
    session: Session, customer_email: str, issue: str
) -> OpenTicketResult:
    email = customer_email.strip()
    issue_text = issue.strip()

    customer_id = session.scalar(select(Customer.id).where(Customer.email == email))
    if customer_id is None:
        return False

    ticket = Ticket(customer_id=customer_id, issue=issue_text, status="open")
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    return _dump_success(OpenTicketSuccess(ticketId=ticket.id))


def openTicket(customerEmail: str, issue: str) -> OpenTicketResult:
    session_factory = get_session_factory()

    with session_factory() as session:
        return open_ticket_with_session(session, customerEmail, issue)
