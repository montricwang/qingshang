from pydantic import BaseModel, Field


class PoemLine(BaseModel):
    line_id: str = Field(..., description="句子 ID，例如 L001")
    line_no: int = Field(..., ge=1, description="全词内句子序号")
    text: str = Field(..., min_length=1, description="词句正文，保留标点")


class PoemSection(BaseModel):
    section_no: int = Field(..., ge=1, description="片段序号，例如 1")
    section_name: str | None = Field(
        default=None,
        description="单调 / 上片 / 下片 / 一叠 / 二叠 / 三叠 / 四叠",
    )
    lines: list[PoemLine]


class PoemCore(BaseModel):
    poem_id: str = Field(..., description="系统内唯一 ID")

    author: str = Field(..., description="作者。无名氏、佚名可直接写作字符串")
    dynasty: str | None = Field(default=None, description="朝代，例如唐、南唐、宋")

    tune_name: str = Field(..., description="词牌名，例如菩萨蛮；失调名可写作'失调名'")
    musical_mode: str | None = Field(default=None, description="宫调，例如大石调")

    title: str | None = Field(
        default=None,
        description="题名，例如赤壁怀古；无题则为空",
    )
    sequence_label: str | None = Field(
        default=None,
        description="原文中出现的序号标签，例如其一、其二",
    )

    preface: str | None = Field(default=None, description="题序 / 小序")

    full_text: str = Field(..., min_length=1, description="完整正文")
    sections: list[PoemSection]

    source: str | None = Field(default=None, description="文本来源")
