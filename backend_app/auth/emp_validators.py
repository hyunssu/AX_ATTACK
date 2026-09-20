"""회원가입 입력 형식 검증 (서버 사이드 최종 방어선).

프론트엔드 검증과 동일한 규칙을 그대로 다시 적용한다 — 클라이언트 검증은
우회될 수 있으므로 신뢰하지 않는다.
"""
import re

ID_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,50}$")
EMP_NO_PATTERN = re.compile(r"^\d{8}$")
PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9]{8,}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

ID_FORMAT_ERROR = "ID should be 3-50 letters, digits, or underscores."
EMP_NO_FORMAT_ERROR = "Employee number should be 8 digits."
PASSWORD_FORMAT_ERROR = "Password should be 8 or more alphanumeric characters."
EMAIL_FORMAT_ERROR = "Invalid email format."


def is_valid_employee_id(value: str) -> bool:
    return bool(ID_PATTERN.match(value or ""))


def is_valid_emp_no(value: str) -> bool:
    return bool(EMP_NO_PATTERN.match(value or ""))


def is_valid_password(value: str) -> bool:
    return bool(PASSWORD_PATTERN.match(value or ""))


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.match(value or ""))
