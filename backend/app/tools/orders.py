from typing import Literal, TypedDict

from pydantic import BaseModel, PositiveInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_session_factory
from database.models import Customer, Order


class OrderStatusItem(BaseModel):
    orderId: PositiveInt
    status: str


class OrderStatusSuccess(BaseModel):
    orders: list[OrderStatusItem]


OrderStatusFailure = Literal["No customer found", "No order found"]


class OrderStatusOutput(BaseModel):
    result: OrderStatusSuccess | OrderStatusFailure


class OrderStatusItemPayload(TypedDict):
    orderId: int
    status: str


class OrderStatusSuccessPayload(TypedDict):
    orders: list[OrderStatusItemPayload]


OrderStatusResult = OrderStatusSuccessPayload | OrderStatusFailure


def _dump_order_status_success(payload: OrderStatusSuccess) -> OrderStatusSuccessPayload:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()

    return payload.dict()


def _validate_order_status_output(
    result: OrderStatusSuccess | OrderStatusFailure,
) -> OrderStatusResult:
    validated_result = OrderStatusOutput(result=result).result
    if isinstance(validated_result, OrderStatusSuccess):
        return _dump_order_status_success(validated_result)

    return validated_result


def order_status_with_session(session: Session, customer_email: str) -> OrderStatusResult:
    email = customer_email.strip()

    customer_id = session.scalar(select(Customer.id).where(Customer.email == email))
    if customer_id is None:
        return _validate_order_status_output("No customer found")

    orders = session.scalars(
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()
    if not orders:
        return _validate_order_status_output("No order found")

    return _validate_order_status_output(
        OrderStatusSuccess(
            orders=[
                OrderStatusItem(orderId=order.id, status=order.status)
                for order in orders
            ]
        )
    )


def OrderStatus(Email: str) -> OrderStatusResult:
    session_factory = get_session_factory()

    with session_factory() as session:
        return order_status_with_session(session, Email)
