from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.tools import open_ticket_with_session
from database.models import Base, Customer, Ticket


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_open_ticket_creates_open_ticket_for_existing_customer():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()
        customer_id = customer.id

        result = open_ticket_with_session(
            session,
            "maya.patel@example.test",
            "Refund request for damaged item",
        )

        assert result is not False
        ticket = session.scalar(select(Ticket).where(Ticket.id == result["ticketId"]))
        ticket_id = ticket.id
        ticket_customer_id = ticket.customer_id
        ticket_issue = ticket.issue
        ticket_status = ticket.status
        ticket_closed_at = ticket.closed_at

    assert result == {"success": True, "ticketId": ticket_id}
    assert ticket_customer_id == customer_id
    assert ticket_issue == "Refund request for damaged item"
    assert ticket_status == "open"
    assert ticket_closed_at is None


def test_open_ticket_returns_false_when_customer_is_missing():
    session_factory = _session_factory()

    with session_factory() as session:
        result = open_ticket_with_session(
            session,
            "missing@example.test",
            "Need help with my order",
        )
        ticket_count = len(session.scalars(select(Ticket)).all())

    assert result is False
    assert ticket_count == 0
