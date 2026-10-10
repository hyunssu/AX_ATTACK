from fastapi import APIRouter, HTTPException, Body, Depends
from auth.service import get_current_user, get_user_role
from .schemas import TermCreateRequest
from .terms import create_term, get_terms, find_term, update_approval 

router = APIRouter(prefix="/api/terms", tags=["terms"])

@router.post("/register")
def register_new_term(data: TermCreateRequest):
    try:
        # terms.py의 create_term 함수 호출
        new_term_id = create_term(
            term_name=data.term_name,
            definition=data.definition,
            keyword=data.keyword,    # 동의어/약어는 keyword 컬럼으로 저장
            category=data.category
        )
        
        return {
            "success": True, 
            "message": "신규 단어가 성공적으로 등록되었습니다.", 
            "term_id": new_term_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"단어 등록 실패: {str(e)}")

@router.get("")
def get_term_list():
    try:
        # terms.py의 get_terms 함수 호출
        terms = get_terms()

        return {
            "success": True,
            "terms": terms
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"단어 조회 실패: {str(e)}"
        )

@router.get("/find")
def find_registered_term(inputword: str):
    try:
        term = find_term(inputword)

        if not term:
            return {
                "success": False,
                "message": "등록된 용어가 없습니다.",
                "term": None
            }

        return {
            "success": True,
            "term": term
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"용어 조회 실패: {str(e)}"
        )

@router.put("/{term_id}/approval")
def update_term_approval(
    term_id: int,
    data: dict = Body(...),
    username: str = Depends(get_current_user),
):
    if get_user_role(username) not in {"ADMIN", "DEVELOPER"}:
        raise HTTPException(status_code=403, detail="용어 승인 상태는 ADMIN 또는 DEVELOPER만 변경할 수 있습니다.")
    try:
        approval_yn = data.get("approval_yn")

        if approval_yn not in ("Y", "N"):
            raise HTTPException(
                status_code=400,
                detail="승인여부는 Y 또는 N만 가능합니다."
            )

        update_approval(
            term_id=term_id,
            approval_yn=approval_yn
        )

        return {
            "success": True,
            "message": "승인여부가 변경되었습니다.",
            "term_id": term_id,
            "approval_yn": approval_yn
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"승인여부 변경 실패: {str(e)}"
        )
