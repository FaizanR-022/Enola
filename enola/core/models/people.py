from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enola.core.enums import ActorSource, InteractionKind
from enola.core.models.base import Base, IdMixin, TimestampMixin, enum_column


class Person(Base, IdMixin, TimestampMixin):
    __tablename__ = "person"

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    company_id: Mapped[int | None] = mapped_column(ForeignKey("company.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    how_we_met: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    can_refer: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Days between touchpoints before the person counts as "going cold". Null = no cadence.
    cadence_days: Mapped[int | None] = mapped_column(Integer)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tags: Mapped[list[PersonTag]] = relationship(
        back_populates="person", cascade="all, delete-orphan", order_by="PersonTag.tag"
    )
    interactions: Mapped[list[Interaction]] = relationship(
        back_populates="person", cascade="all, delete-orphan", order_by="Interaction.occurred_at.desc()"
    )


class PersonTag(Base, IdMixin):
    __tablename__ = "person_tag"
    __table_args__ = (UniqueConstraint("person_id", "tag"),)

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=False)
    tag: Mapped[str] = mapped_column(String(60), nullable=False, index=True)

    person: Mapped[Person] = relationship(back_populates="tags")


class Interaction(Base, IdMixin, TimestampMixin):
    __tablename__ = "interaction"

    person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[InteractionKind] = enum_column(InteractionKind, nullable=False, default=InteractionKind.NOTE)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[ActorSource] = enum_column(ActorSource, nullable=False, default=ActorSource.YOU)

    person: Mapped[Person] = relationship(back_populates="interactions")
