from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.tools import customer_information_with_session
from app.tools.customers import CustomerInformationOutput
from database.models import Base, Customer


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_customer_information_returns_customer_for_existing_email():
    session_factory = _session_factory()
    created_at = datetime(2026, 9, 27, 9, 30, tzinfo=UTC).replace(tzinfo=None)

    with session_factory() as session:
        customer = Customer(
            email="maya.patel@example.test",
            name="Maya Patel",
            created_at=created_at,
        )
        session.add(customer)
        session.commit()

        result = customer_information_with_session(session, "maya.patel@example.test")

    assert result == {
        "id": customer.id,
        "email": "maya.patel@example.test",
        "name": "Maya Patel",
        "createdAt": created_at,
    }


def test_customer_information_trims_email_before_lookup():
    session_factory = _session_factory()

    with session_factory() as session:
        customer = Customer(email="maya.patel@example.test", name=None)
        session.add(customer)
        session.commit()

        result = customer_information_with_session(
            session, "  maya.patel@example.test  "
        )

    assert result["email"] == "maya.patel@example.test"
    assert result["name"] is None


def test_customer_information_returns_no_customer_found_when_customer_is_missing():
    session_factory = _session_factory()

    with session_factory() as session:
        result = customer_information_with_session(session, "missing@example.test")

    assert result == "No customer found"


def test_customer_information_output_validation_rejects_unknown_result():
    with pytest.raises(ValidationError):
        CustomerInformationOutput(result="Customer missing")
