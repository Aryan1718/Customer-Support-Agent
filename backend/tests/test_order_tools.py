from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.tools import order_status_with_session
from app.tools.orders import OrderStatusOutput
from database.models import Base, Customer, Order


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_order_status_returns_most_recent_orders_for_customer():
    session_factory = _session_factory()
    now = datetime.now(UTC).replace(tzinfo=None)

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        other_customer = Customer(email="rohan.gupta@example.test", name="Rohan Gupta")
        session.add_all([customer, other_customer])
        session.commit()

        old_order = Order(
            customer_id=customer.id,
            status="delivered",
            total_amount=Decimal("24.99"),
            created_at=now - timedelta(days=2),
        )
        recent_order = Order(
            customer_id=customer.id,
            status="processing",
            total_amount=Decimal("49.99"),
            created_at=now,
        )
        other_order = Order(
            customer_id=other_customer.id,
            status="pending",
            total_amount=Decimal("10.00"),
            created_at=now + timedelta(days=1),
        )
        session.add_all([old_order, recent_order, other_order])
        session.commit()

        result = order_status_with_session(session, "maya.patel@example.test")

    assert result == {
        "orders": [
            {"orderId": recent_order.id, "status": "processing"},
            {"orderId": old_order.id, "status": "delivered"},
        ]
    }


def test_order_status_returns_no_customer_found_when_customer_is_missing():
    session_factory = _session_factory()

    with session_factory() as session:
        result = order_status_with_session(session, "missing@example.test")

    assert result == "No customer found"


def test_order_status_returns_no_order_found_when_customer_has_no_orders():
    session_factory = _session_factory()

    with session_factory() as session:
        session.add(Customer(email="maya.patel@example.test", name="Maya Patel"))
        session.commit()

        result = order_status_with_session(session, "maya.patel@example.test")

    assert result == "No order found"


def test_order_status_output_validation_rejects_unknown_result():
    with pytest.raises(ValidationError):
        OrderStatusOutput(result="Customer missing")
