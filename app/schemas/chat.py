from pydantic import BaseModel, Field


class ChatTestRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, max_length=1000, description="用户输入的一句话"
    )


class ChatTestResponse(BaseModel):
    reply: str
