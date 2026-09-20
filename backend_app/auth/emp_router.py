"""직원 회원관리 로그인/회원가입 API (users_kyj 기반).

과거엔 employee_info 전용 테이블 + 별도 JWT를 썼지만, users_kyj로
통합되면서 로그인 주체가 users_kyj.username이 됐다. 그래서 토큰 발급/검증도
auth/service.py의 create_access_token()/get_current_user()를 그대로 쓴다 —
다른 라우터(chat/manuals/faq)와 완전히 같은 인증 경로를 공유한다.
"""
from fastapi import APIRouter, Depends, HTTPException

from auth.emp_config import EMP_EMAIL_VERIFICATION_TTL_MINUTES, LOGIN_MAIL_ENABLED
from auth.emp_meta import list_countries, list_languages, list_permissions, list_positions, list_teams
from auth.emp_profile import employee_email_taken_by_other, update_employee_profile
from auth.emp_register import create_employee, employee_email_exists, employee_id_exists, employee_no_exists
from auth.emp_schemas import (
    EmailVerifyConfirmBody,
    EmailVerifyRequestBody,
    EmployeeLoginRequest,
    EmployeeLoginResponse,
    EmployeeMeResponse,
    EmployeeRegisterRequest,
    EmployeeUpdateRequest,
)
from auth.emp_service import get_employee, verify_employee_password
from auth.emp_validators import (
    EMAIL_FORMAT_ERROR,
    EMP_NO_FORMAT_ERROR,
    ID_FORMAT_ERROR,
    PASSWORD_FORMAT_ERROR,
    is_valid_email,
    is_valid_emp_no,
    is_valid_employee_id,
    is_valid_password,
)
from auth.emp_verify import confirm_verification_code, is_email_verified, request_verification_code
from auth.service import create_access_token, get_current_user

router = APIRouter(prefix="/api/employees", tags=["employee-auth"])


def _reraise_as_http_500(exc: Exception):
    """예상 못한 예외를 텍스트 500 대신 진단 가능한 JSON 500으로 바꾼다.

    main.py의 전역 핸들러는 ProgrammingError만 잡으므로, 그 외 예외(연결 오류,
    아직 실행 안 된 DDL로 인한 다른 종류의 DB 오류 등)는 원래 FastAPI 기본
    텍스트 500으로 떨어져 프론트의 res.json()이 깨진다. 여기서 잡아 실제
    예외 메시지를 그대로 detail에 담아 내려서 원인을 바로 알 수 있게 한다.
    """
    raise HTTPException(status_code=500, detail=f"employee 기능 오류: {exc}") from exc


@router.post("/login", response_model=EmployeeLoginResponse)
def login(req: EmployeeLoginRequest):
    try:
        if not verify_employee_password(req.id, req.password):
            raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

        employee = get_employee(req.id)
        token = create_access_token(req.id)
        return EmployeeLoginResponse(
            access_token=token,
            id=employee["id"],
            team_code=employee["team_code"],
            position_code=employee["position_code"],
            permission_code=employee["permission_code"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        _reraise_as_http_500(exc)


@router.get("/me", response_model=EmployeeMeResponse)
def get_me(employee_id: str = Depends(get_current_user)):
    try:
        employee = get_employee(employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        return EmployeeMeResponse(
            id=employee["id"],
            username=employee["username"],
            email=employee["email"],
            team_code=employee["team_code"],
            position_code=employee["position_code"],
            permission_code=employee["permission_code"],
            lang_code=employee["lang_code"],
            countries=list(employee["countries"] or []),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _reraise_as_http_500(exc)


@router.put("/me")
def update_me(req: EmployeeUpdateRequest, employee_id: str = Depends(get_current_user)):
    """마이페이지 수정. ID·permission_code는 이 API로 바꿀 수 없다."""
    try:
        if req.password and not is_valid_password(req.password):
            raise HTTPException(status_code=422, detail=PASSWORD_FORMAT_ERROR)
        if not is_valid_email(req.email):
            raise HTTPException(status_code=422, detail=EMAIL_FORMAT_ERROR)
        if not is_email_verified(req.email):
            raise HTTPException(status_code=422, detail="이메일 인증을 완료해 주세요.")
        if employee_email_taken_by_other(employee_id, req.email):
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")

        update_employee_profile(
            employee_id,
            password=req.password,
            email=req.email,
            team_code=req.team_code,
            position_code=req.position_code,
            lang_code=req.lang_code,
            countries=req.countries,
        )
        return {"message": "정보가 수정되었습니다."}
    except HTTPException:
        raise
    except Exception as exc:
        _reraise_as_http_500(exc)


@router.get("/meta")
def get_signup_meta():
    """회원가입 화면의 select box(조직/직급/권한/언어/담당국가)를 채우기 위한 목록."""
    try:
        return {
            "teams": list_teams(),
            "positions": list_positions(),
            "permissions": list_permissions(),
            "languages": list_languages(),
            "countries": list_countries(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        _reraise_as_http_500(exc)


@router.post("/verify-email/request")
def request_email_verification(body: EmailVerifyRequestBody):
    try:
        if not is_valid_email(body.email):
            raise HTTPException(status_code=422, detail=EMAIL_FORMAT_ERROR)

        code = request_verification_code(body.email)
        response = {"expires_in_seconds": EMP_EMAIL_VERIFICATION_TTL_MINUTES * 60}
        if not LOGIN_MAIL_ENABLED:
            # 메일 발송이 꺼져 있는 개발 환경에서도 흐름을 끝까지 테스트할 수 있도록
            # 발급된 코드를 응답에 함께 내려준다.
            response["dev_code"] = code
        return response
    except HTTPException:
        raise
    except Exception as exc:
        _reraise_as_http_500(exc)


@router.post("/verify-email/confirm")
def confirm_email_verification(body: EmailVerifyConfirmBody):
    try:
        if not confirm_verification_code(body.email, body.code):
            raise HTTPException(status_code=400, detail="인증번호가 일치하지 않거나 만료되었습니다.")
        return {"verified": True}
    except HTTPException:
        raise
    except Exception as exc:
        _reraise_as_http_500(exc)


@router.post("/register", status_code=201)
def register(req: EmployeeRegisterRequest):
    try:
        if not is_valid_employee_id(req.id):
            raise HTTPException(status_code=422, detail=ID_FORMAT_ERROR)
        if not is_valid_emp_no(req.emp_no):
            raise HTTPException(status_code=422, detail=EMP_NO_FORMAT_ERROR)
        if not is_valid_password(req.password):
            raise HTTPException(status_code=422, detail=PASSWORD_FORMAT_ERROR)
        if not is_valid_email(req.email):
            raise HTTPException(status_code=422, detail=EMAIL_FORMAT_ERROR)
        if not is_email_verified(req.email):
            raise HTTPException(status_code=422, detail="이메일 인증을 완료해 주세요.")
        if employee_id_exists(req.id):
            raise HTTPException(status_code=409, detail="이미 사용 중인 ID입니다.")
        if employee_no_exists(int(req.emp_no)):
            raise HTTPException(status_code=409, detail="이미 사용 중인 사번입니다.")
        if employee_email_exists(req.email):
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")

        create_employee(
            emp_no=int(req.emp_no),
            employee_id=req.id,
            password=req.password,
            email=req.email,
            team_code=req.team_code,
            position_code=req.position_code,
            permission_code=req.permission_code,
            lang_code=req.lang_code,
            countries=req.countries,
        )
        return {"message": "회원가입이 완료되었습니다."}
    except HTTPException:
        raise
    except Exception as exc:
        _reraise_as_http_500(exc)
