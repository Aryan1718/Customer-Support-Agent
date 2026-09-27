from database.connection import get_engine
from database.models import Base


def create_tables() -> None:
    Base.metadata.create_all(bind=get_engine())


if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully.")

