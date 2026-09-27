from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, PositiveInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_session_factory
from database.models import Customer


class CustomerInformationSuccess(BaseModel):
    id: PositiveInt
    email: str
    name: str | None
    createdAt: datetime


CustomerInformationFailure = Literal["No customer found"]


class CustomerInformationOutput(BaseModel):
    result: CustomerInformationSuccess | CustomerInformationFailure


class CustomerInformationPayload(TypedDict):
    id: int
    email: str
    name: str | None
    createdAt: datetime


CustomerInformationResult = CustomerInformationPayload | CustomerInformationFailure


def _dump_customer_information_success(
    payload: CustomerInformationSuccess,
) -> CustomerInformationPayload:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()

    return payload.dict()


def _validate_customer_information_output(
    result: CustomerInformationSuccess | CustomerInformationFailure,
) -> CustomerInformationResult:
    validated_result = CustomerInformationOutput(result=result).result
    if isinstance(validated_result, CustomerInformationSuccess):
        return _dump_customer_information_success(validated_result)

    return validated_result


def customer_information_with_session(
    session: Session, customer_email: str
) -> CustomerInformationResult:
    email = customer_email.strip()

    customer = session.scalar(select(Customer).where(Customer.email == email))
    if customer is None:
        return _validate_customer_information_output("No customer found")

    return _validate_customer_information_output(
        CustomerInformationSuccess(
            id=customer.id,
            email=customer.email,
            name=customer.name,
            createdAt=customer.created_at,
        )
    )


def customerInformation(email: str) -> CustomerInformationResult:
    session_factory = get_session_factory()

    with session_factory() as session:
        return customer_information_with_session(session, email)
