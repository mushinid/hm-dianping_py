from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "tb_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(11), nullable=False, unique=True)
    password: Mapped[str | None] = mapped_column(String(128), default="", server_default=text("''"))
    nick_name: Mapped[str | None] = mapped_column(String(32), default="", server_default=text("''"))
    icon: Mapped[str | None] = mapped_column(String(255), default="", server_default=text("''"))
    create_time: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )


class UserInfo(Base):
    __tablename__ = "tb_user_info"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    city: Mapped[str | None] = mapped_column(String(64), default="", server_default=text("''"))
    introduce: Mapped[str | None] = mapped_column(String(128))
    fans: Mapped[int | None] = mapped_column(Integer, default=0, server_default=text("0"))
    followee: Mapped[int | None] = mapped_column(Integer, default=0, server_default=text("0"))
    gender: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default=text("0"))
    birthday: Mapped[date | None] = mapped_column(Date)
    credits: Mapped[int | None] = mapped_column(Integer, default=0, server_default=text("0"))
    level: Mapped[int | None] = mapped_column(Integer, default=0, server_default=text("0"))
    create_time: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
