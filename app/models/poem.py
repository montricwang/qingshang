from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PoemModel(Base):
    __tablename__: str = "poems"

    __table_args__ = (
        UniqueConstraint(
            "author",
            "author_order",
            name="uq_poems_author_author_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    poem_id: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True,
        nullable=False,
        comment="系统内稳定 ID，例如 libai-0001、sushi-0001、zhoubangyan-0001",
    )

    author_order: Mapped[int] = mapped_column(
        nullable=False,
        comment="在该作者词作中的排列顺序",
    )

    author: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="作者。无名氏、佚名直接作为字符串保存",
    )
    dynasty: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        comment="朝代，例如唐、南唐、宋",
    )

    tune_name: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="词牌名，例如菩萨蛮；失调名可写作「失调名」",
    )
    musical_mode: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="宫调，例如中吕宫、大石、商调",
    )

    title: Mapped[str | None] = mapped_column(
        String(200),
        index=True,
        nullable=True,
        comment="题名，例如赤壁怀古；无题则为空",
    )
    series_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="套词标签，例如其一、其二、第二、十之一；非套词为空；「又」不保存",
    )

    preface: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="题序 / 小序",
    )

    full_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="完整正文，不含题序；由 sections/lines 自动拼接生成，用于展示、搜索和 AI 上下文",
    )

    source: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        comment="文本来源",
    )

    sections: Mapped[list[PoemSectionModel]] = relationship(
        back_populates="poem",
        cascade="all, delete-orphan",
        order_by="PoemSectionModel.section_no",
    )


class PoemSectionModel(Base):
    __tablename__: str = "poem_sections"

    __table_args__ = (
        UniqueConstraint(
            "poem_db_id",
            "section_no",
            name="uq_poem_sections_poem_db_id_section_no",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    poem_db_id: Mapped[int] = mapped_column(
        ForeignKey("poems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    section_no: Mapped[int] = mapped_column(
        nullable=False,
        comment="片段序号，例如 1、2",
    )
    section_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="片段名称。双调可为上片 / 下片；多叠可为第一叠 / 第二叠 / 第三叠 / 第四叠；单片可为空",
    )

    poem: Mapped[PoemModel] = relationship(back_populates="sections")

    lines: Mapped[list[PoemLineModel]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="PoemLineModel.section_line_no",
    )


class PoemLineModel(Base):
    __tablename__: str = "poem_lines"

    __table_args__ = (
        UniqueConstraint(
            "poem_db_id",
            "global_line_no",
            name="uq_poem_lines_poem_db_id_global_line_no",
        ),
        UniqueConstraint(
            "section_db_id",
            "section_line_no",
            name="uq_poem_lines_section_db_id_section_line_no",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    poem_db_id: Mapped[int] = mapped_column(
        ForeignKey("poems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section_db_id: Mapped[int] = mapped_column(
        ForeignKey("poem_sections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    global_line_no: Mapped[int] = mapped_column(
        nullable=False,
        comment="全词内句子序号，用于稳定定位、排序和缓存",
    )
    section_line_no: Mapped[int] = mapped_column(
        nullable=False,
        comment="当前片段内句子序号，例如上片第 1 句、下片第 2 句",
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="词句正文，保留标点",
    )

    section: Mapped[PoemSectionModel] = relationship(back_populates="lines")
