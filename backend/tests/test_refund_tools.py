from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.tools import refund_with_session
from app.tools.refunds import RefundOutput
from database.models import Base, Customer, Order


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_refund_returns_no_customer_found_when_customer_is_missing():
    session_factory = _session_factory()

    with session_factory() as session:
        result = refund_with_session(session, "missing@example.test", 1)

    assert result == "No customer found"


def test_refund_returns_no_order_exists_when_order_is_missing():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()

        result = refund_with_session(session, "maya.patel@example.test", 999)

    assert result == "No order exists"


def test_refund_returns_no_order_exists_for_another_customers_order():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        other_customer = Customer(email="rohan.gupta@example.test", name="Rohan Gupta")
        session.add_all([customer, other_customer])
        session.commit()

        order = Order(
            customer_id=other_customer.id,
            status="delivered",
            total_amount=Decimal("4.99"),
        )
        session.add(order)
        session.commit()

        result = refund_with_session(session, "maya.patel@example.test", order.id)

    assert result == "No order exists"


def test_refund_auto_approves_when_refund_amount_is_less_than_ten_dollars():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()

        order = Order(
            customer_id=customer.id,
            status="delivered",
            total_amount=Decimal("9.99"),
        )
        session.add(order)
        session.commit()

        result = refund_with_session(session, "maya.patel@example.test", order.id)

    assert result is True


def test_refund_requires_human_approval_when_refund_amount_is_ten_or_more():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()

        order = Order(
            customer_id=customer.id,
            status="delivered",
            total_amount=Decimal("10.00"),
        )
        session.add(order)
        session.commit()

        result = refund_with_session(session, "maya.patel@example.test", order.id)

    assert result == "Human Approval"


def test_refund_output_validation_rejects_unknown_result():
    with pytest.raises(ValidationError):
        RefundOutput(result="Refund approved")
