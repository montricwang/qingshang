"""SQLAlchemy 所有 ORM 模型共同继承的基类。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 模型基类；SQLAlchemy 会把子类声明登记到 metadata。"""
