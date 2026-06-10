from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatTestRequest, ChatTestResponse
from app.services.deepseek import chat_with_deepseek

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/test", response_model=ChatTestResponse)
async def test_chat(request: ChatTestRequest):
    try:
        reply = await chat_with_deepseek(request.message)
        return ChatTestResponse(reply=reply)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=502, detail="Deepseek call failed") from exc
