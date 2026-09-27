"""신규 직원 회원관리 기능이 사용하는 테이블 이름의 단일 정의점.

기존 backend_app/db_tables.py(_kyj 전용 정의)와는 별개로 관리한다.

users_kyj 통합 이후 employee_info는 더 이상 쓰지 않는다 — 직원 정보는
db_tables.USERS(users_kyj)를 그대로 참조한다.
"""

TEAM_INFO = "team_info"
POSITION_INFO = "position_info"
PERMISSION_INFO = "permission_info"
LANGUAGE_INFO = "language_info"
COUNTRIES_INFO = "countries_info"
EMAIL_VERIFICATIONS = "email_verifications"
