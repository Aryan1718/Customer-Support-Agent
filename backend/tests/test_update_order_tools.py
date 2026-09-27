from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.tools.orders as order_tools
from app.tools import update_order_with_session
from app.tools.orders import UpdateOrderOutput
from database.models import Base, Customer, Order


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_update_order_returns_no_customer_found_when_customer_is_missing():
    session_factory = _session_factory()

    with session_factory() as session:
        result = update_order_with_session(session, "missing@example.test", 1)

    assert result == "No customer found"


def test_update_order_returns_no_order_found_when_order_is_missing():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()

        result = update_order_with_session(session, "maya.patel@example.test", 999)

    assert result == "No order found"


def test_update_order_returns_no_order_found_for_another_customers_order():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        other_customer = Customer(email="rohan.gupta@example.test", name="Rohan Gupta")
        session.add_all([customer, other_customer])
        session.commit()

        order = Order(
            customer_id=other_customer.id,
            status="processing",
            total_amount=Decimal("24.99"),
        )
        session.add(order)
        session.commit()

        result = update_order_with_session(session, "maya.patel@example.test", order.id)

    assert result == "No order found"


def test_update_order_returns_can_not_update_when_new_amount_is_greater(monkeypatch):
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()

        order = Order(
            customer_id=customer.id,
            status="processing",
            total_amount=Decimal("24.99"),
        )
        session.add(order)
        session.commit()

        monkeypatch.setattr(
            order_tools,
            "_calculate_new_total_amount",
            lambda order: Decimal("25.00"),
        )

        result = update_order_with_session(session, "maya.patel@example.test", order.id)

    assert result == "Can not update"


def test_update_order_returns_can_not_update_when_new_amount_is_less(monkeypatch):
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()

        order = Order(
            customer_id=customer.id,
            status="processing",
            total_amount=Decimal("24.99"),
        )
        session.add(order)
        session.commit()

        monkeypatch.setattr(
            order_tools,
            "_calculate_new_total_amount",
            lambda order: Decimal("24.98"),
        )

        result = update_order_with_session(session, "maya.patel@example.test", order.id)

    assert result == "Can not update"


def test_update_order_updates_when_amount_is_unchanged():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name="Maya Patel")
        session.add(customer)
        session.commit()

        order = Order(
            customer_id=customer.id,
            status="processing",
            total_amount=Decimal("24.99"),
        )
        session.add(order)
        session.commit()

        result = update_order_with_session(session, "  maya.patel@example.test  ", order.id)

    assert result is True


def test_update_order_output_validation_rejects_unknown_result():
    with pytest.raises(ValidationError):
        UpdateOrderOutput(result="Order updated")
