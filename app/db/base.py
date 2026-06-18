"""SQLAlchemy 所有 ORM 模型共同继承的基类。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """声明式模型基类。

    SQLAlchemy 会在子类定义完成时读取 ``__tablename__``、``mapped_column`` 和
    ``relationship``，并把表结构登记到 ``Base.metadata``。这些类既描述数据库表，
    也用于承载查询结果，但定义类本身不会立即创建数据库表。
    """
