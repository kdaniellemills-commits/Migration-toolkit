"""Target schema: where migrated data lands."""
from sqlalchemy import Column, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    legacy_id = Column(Text, nullable=False, unique=True)  # id in the source system
    name = Column(Text, nullable=False)
    city = Column(Text)
    state = Column(Text)
    phone = Column(Text)
    created = Column(Date)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    legacy_id = Column(Text, nullable=False, unique=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    first_name = Column(Text)
    last_name = Column(Text)
    email = Column(Text, nullable=False, unique=True)
    phone = Column(Text)
    title = Column(Text)
