from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user
from rag import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    input_message: str
    manual_id: Optional[int] = None


@router.post("")
def chat(req: ChatRequest, username: str = Depends(get_current_user)):
    try:
        output_message = answer_question(req.input_message, req.manual_id)
        return {"output_message": output_message}
    except Exception as e:
        return {"output_message": f"LLM 호출 에러: {str(e)}"}
