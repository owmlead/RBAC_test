"""
SQLAlchemy 声明式基类。

所有 ORM 模型继承自 Base，通过 Base.metadata 统一管理表元数据。
init_db() 通过 Base.metadata.create_all() 遍历所有注册模型并建表。

模型定义示例:
    from src.rbac.db.base import Base
    from sqlalchemy.orm import Mapped, mapped_column

    class User(Base):
        __tablename__ = "user"
        id: Mapped[int] = mapped_column(primary_key=True)
        ...
"""
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    SQLAlchemy 声明式基类。

    继承自 DeclarativeBase，提供表映射、类型注解支持等基础设施。
    所有模型文件通过继承此类自动注册到 Base.metadata。
    """
    pass
