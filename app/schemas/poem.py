"""诗词 API 与数据脚本共用的 Pydantic 数据结构。

这些类不是数据库表。它们描述“允许进入或离开程序的数据长什么样”，Pydantic 会
在 ``model_validate`` 时检查类型和约束，并在 ``model_dump`` 时转成普通数据。
"""

from pydantic import BaseModel, ConfigDict, Field


class PoemLine(BaseModel):
    """一句词的对外数据结构。"""

    # 允许从 ORM 对象的属性读取值，而不只接受字典。
    model_config = ConfigDict(from_attributes=True)

    global_line_no: int = Field(
        ...,
        ge=1,
        description="全词内句子序号，用于稳定定位、排序和缓存",
    )
    section_line_no: int = Field(
        ...,
        ge=1,
        description="当前片段内句子序号，例如上片第 1 句、下片第 2 句",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="词句正文，保留标点",
    )


class PoemSection(BaseModel):
    """一个片段及其全部词句。验证本对象时还会递归验证 lines。"""

    model_config = ConfigDict(from_attributes=True)

    section_no: int = Field(
        ...,
        ge=1,
        description="片段序号，例如 1",
    )
    section_name: str | None = Field(
        default=None,
        description="片段名称。双调可为上片 / 下片；多叠可为第一叠 / 第二叠 / 第三叠 / 第四叠；单片可为空",
    )
    lines: list[PoemLine]


class PoemListItem(BaseModel):
    """列表接口需要的摘要字段，不包含正文和片段。"""

    model_config = ConfigDict(from_attributes=True)

    poem_id: str = Field(
        ...,
        description="系统内唯一 ID，形如 libai-0001",
    )

    author_order: int = Field(
        ...,
        ge=1,
        description="在该作者词作中的排列顺序",
    )

    author: str = Field(
        ...,
        description="作者（含无名氏）",
    )
    dynasty: str | None = Field(
        default=None,
        description="朝代，例如唐、南唐、宋",
    )

    tune_name: str = Field(
        ...,
        description="词牌名，例如菩萨蛮（含「失调名」）",
    )
    musical_mode: str | None = Field(
        default=None,
        description="宫调，例如大石调",
    )

    title: str | None = Field(
        default=None,
        description="题名，例如赤壁怀古；无题则为空",
    )

    series_label: str | None = Field(
        default=None,
        description="套词标签，例如其一、其二、第二、十之一；非套词为空",
    )


class PoemCore(PoemListItem):
    """完整诗词结构。

    继承 PoemListItem 表示先复用摘要字段，再增加详情字段。清洗脚本用它验证生成的
    JSON，详情接口也用它限制最终响应字段。
    """

    preface: str | None = Field(
        default=None,
        description="题序 / 小序",
    )

    full_text: str = Field(
        ...,
        min_length=1,
        description="完整正文",
    )
    sections: list[PoemSection]

    source: str | None = Field(
        default=None,
        description="文本来源",
    )
