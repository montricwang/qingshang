"""诗词数据库 ORM 模型。

ORM（对象关系映射）让 Python 对象与数据库记录相互转换。``mapped_column`` 不是
在此刻存入某个值，而是在类创建阶段向 SQLAlchemy 声明列；查询后，同名属性才会
装入某一行的真实数据。``relationship`` 声明对象之间的导航关系，不直接新增列。
"""

from __future__ import annotations

# SQLAlchemy 的列类型、外键和数据库约束。
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
# ORM 类型标注、列声明和对象关系声明工具。
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PoemModel(Base):
    """一首词的主记录，对应数据库 ``poems`` 表。"""

    __tablename__: str = "poems"

    # 组合唯一约束保证同一作者不能出现重复的排列序号；数据库负责最终兜底。
    __table_args__ = (
        UniqueConstraint(
            "author",
            "author_order",
            name="uq_poems_author_author_order",
        ),
    )

    # Mapped[int] 同时服务于类型检查和 SQLAlchemy；mapped_column 描述真实数据库列。
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

    # relationship 根据外键把一首词的多个片段组织成 Python 列表。
    # 默认查询主表时它未必立刻加载；本项目详情查询使用 selectinload 主动预加载。
    sections: Mapped[list[PoemSectionModel]] = relationship(
        back_populates="poem",
        cascade="all, delete-orphan",
        order_by="PoemSectionModel.section_no",
    )


class PoemSectionModel(Base):
    """词的一个片段，例如上片或下片，对应 ``poem_sections`` 表。"""

    __tablename__: str = "poem_sections"

    __table_args__ = (
        UniqueConstraint(
            "poem_db_id",
            "section_no",
            name="uq_poem_sections_poem_db_id_section_no",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 外键在数据库层保证 section 指向一条真实存在的 poem 记录。
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

    # back_populates 把双向关系配对：section.poem 与 poem.sections 保持一致。
    poem: Mapped[PoemModel] = relationship(back_populates="sections")

    lines: Mapped[list[PoemLineModel]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="PoemLineModel.section_line_no",
    )


class PoemLineModel(Base):
    """一个最小解释单位（通常是一句词），对应 ``poem_lines`` 表。"""

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

    # 从行对象导航回所属片段；真正的关联依据是 section_db_id 外键。
    section: Mapped[PoemSectionModel] = relationship(back_populates="lines")
