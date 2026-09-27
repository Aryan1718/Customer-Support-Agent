from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from database.connection import get_session_factory
from database.models import Customer, Order, Ticket

DUMMY_EMAIL_DOMAIN = "example.test"


CUSTOMERS = [
    ("Aarav Sharma", "aarav.sharma"),
    ("Maya Patel", "maya.patel"),
    ("Rohan Gupta", "rohan.gupta"),
    ("Isha Mehta", "isha.mehta"),
    ("Kabir Khan", "kabir.khan"),
    ("Anika Rao", "anika.rao"),
    ("Vihaan Singh", "vihaan.singh"),
    ("Sara Thomas", "sara.thomas"),
    ("Neil Kapoor", "neil.kapoor"),
    ("Priya Nair", "priya.nair"),
]

ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]

TICKET_ISSUES = [
    "Where is my order?",
    "Need to update shipping address",
    "Refund request for damaged item",
    "Payment charged twice",
    "Item missing from package",
    "Unable to apply discount code",
    "Need invoice copy",
    "Product arrived late",
    "Wrong item received",
    "Account email update request",
]


def _created_at(days_ago: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)


def seed_dummy_data() -> None:
    session_factory = get_session_factory()

    with session_factory() as session:
        existing_dummy_count = session.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.email.like(f"%@{DUMMY_EMAIL_DOMAIN}"))
        )

        if existing_dummy_count:
            print("Dummy data already exists. No new records were inserted.")
            return

        customers = [
            Customer(
                name=name,
                email=f"{email_prefix}@{DUMMY_EMAIL_DOMAIN}",
                created_at=_created_at(index + 20),
            )
            for index, (name, email_prefix) in enumerate(CUSTOMERS)
        ]
        session.add_all(customers)
        session.flush()

        orders = []
        for index in range(30):
            customer = customers[index % len(customers)]
            orders.append(
                Order(
                    customer_id=customer.id,
                    status=ORDER_STATUSES[index % len(ORDER_STATUSES)],
                    total_amount=Decimal("24.99") + (Decimal(index) * Decimal("7.50")),
                    created_at=_created_at(30 - index),
                )
            )

        tickets = []
        for index in range(40):
            customer = customers[index % len(customers)]
            is_closed = index % 3 != 0
            created_at = _created_at(40 - index)
            tickets.append(
                Ticket(
                    customer_id=customer.id,
                    issue=TICKET_ISSUES[index % len(TICKET_ISSUES)],
                    status="closed" if is_closed else "open",
                    created_at=created_at,
                    closed_at=created_at + timedelta(days=2) if is_closed else None,
                )
            )

        session.add_all(orders)
        session.add_all(tickets)
        session.commit()

    print("Inserted 10 customers, 30 orders, and 40 tickets.")


if __name__ == "__main__":
    seed_dummy_data()
