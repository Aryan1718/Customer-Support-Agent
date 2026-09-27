from decimal import Decimal
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

UpdateOrderResult = Literal[True, "No customer found", "No order found", "Can not update"]


class UpdateOrderOutput(BaseModel):
    result: UpdateOrderResult


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


def _validate_update_order_output(result: UpdateOrderResult) -> UpdateOrderResult:
    return UpdateOrderOutput(result=result).result


def _calculate_new_total_amount(order: Order) -> Decimal:
    return Decimal(order.total_amount)


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


def update_order_with_session(
    session: Session, customer_email: str, order_id: int
) -> UpdateOrderResult:
    email = customer_email.strip()

    customer_id = session.scalar(select(Customer.id).where(Customer.email == email))
    if customer_id is None:
        return _validate_update_order_output("No customer found")

    order = session.scalar(
        select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
    )
    if order is None:
        return _validate_update_order_output("No order found")

    old_amount = Decimal(order.total_amount)
    new_amount = _calculate_new_total_amount(order)
    if new_amount > old_amount or new_amount < old_amount:
        return _validate_update_order_output("Can not update")

    order.total_amount = new_amount
    session.commit()
    session.refresh(order)

    return _validate_update_order_output(True)


def updateOrder(Email: str, OrderId: int) -> UpdateOrderResult:
    session_factory = get_session_factory()

    with session_factory() as session:
        return update_order_with_session(session, Email, OrderId)
