"""카테고리 편집 및 매뉴얼 관리 권한.

manual_categories.org_code가 team_info와 연결된 카테고리는 그 팀/파트
소속 직원만 수정할 수 있고, org_code가 없는 카테고리(조직에 매칭되지
않는 카테고리)는 ADMIN만 수정할 수 있다. 조회(GET)는 로그인한 모든
사용자에게 열려 있으며 이 모듈은 쓰기 요청만 가로막는다.
제목 수정, 본문 편집, 삭제, 복원 모두 동일한 파트 권한을 적용한다.
"""
from fastapi import HTTPException
from sqlalchemy import text

from auth.emp_service import get_employee
from db import engine


def category_org_code(category: str | None) -> str | None:
    if not category:
        return None
    with engine.connect() as conn:
        try:
            return conn.execute(
                text("SELECT org_code FROM manual_categories WHERE name = :name"),
                {"name": category},
            ).scalar_one_or_none()
        except Exception:
            # org_code 컬럼 마이그레이션 전에는 팀 매칭 없이 ADMIN 전용으로 취급한다.
            return None


def manual_primary_category(manual_id: int) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT categories[1] FROM manuals WHERE id = :id AND deleted_at IS NULL"),
            {"id": manual_id},
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail="매뉴얼을 찾을 수 없습니다.")
    return row[0]


def can_edit_category(username: str, category: str | None) -> bool:
    employee = get_employee(username)
    if employee and employee["permission_code"] == "ADMIN":
        return True
    org_code = category_org_code(category)
    if not org_code:
        return False
    return bool(employee and employee["team_code"] == org_code)


def require_category_edit(username: str, category: str | None) -> None:
    if not can_edit_category(username, category):
        raise HTTPException(status_code=403, detail="소속 파트의 매뉴얼만 추가하거나 수정할 수 있습니다.")


def require_manual_edit(username: str, manual_id: int) -> None:
    require_category_edit(username, manual_primary_category(manual_id))


def require_manual_manage(username: str, manual) -> None:
    category = manual["categories"][0] if manual["categories"] else None
    require_category_edit(username, category)
