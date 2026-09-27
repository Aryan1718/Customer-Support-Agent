from decimal import Decimal
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import get_session_factory
from database.models import Customer, Order


RefundResult = Literal[True, "Human Approval", "No customer found", "No order exists"]

AUTO_REFUND_LIMIT = Decimal("10.00")


class RefundOutput(BaseModel):
    result: RefundResult


def _validate_refund_output(result: RefundResult) -> RefundResult:
    return RefundOutput(result=result).result


def refund_with_session(session: Session, customer_email: str, order_id: int) -> RefundResult:
    email = customer_email.strip()

    customer_id = session.scalar(select(Customer.id).where(Customer.email == email))
    if customer_id is None:
        return _validate_refund_output("No customer found")

    order = session.scalar(
        select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
    )
    if order is None:
        return _validate_refund_output("No order exists")

    refund_amount = Decimal(order.total_amount)
    if refund_amount < AUTO_REFUND_LIMIT:
        return _validate_refund_output(True)

    return _validate_refund_output("Human Approval")


def Refund(email: str, orderID: int) -> RefundResult:
    session_factory = get_session_factory()

    with session_factory() as session:
        return refund_with_session(session, email, orderID)
