from pydantic import BaseModel, ConfigDict, Field


class PoemLine(BaseModel):
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
