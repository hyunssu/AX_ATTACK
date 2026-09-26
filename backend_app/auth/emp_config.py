"""신규 직원 회원관리 로그인 전용 설정.

users_kyj 통합 이후 로그인은 auth/service.py의 create_access_token()/
get_current_user()를 그대로 쓴다 — 더 이상 별도 JWT 시크릿/만료시간을
쓰지 않는다(과거엔 employee_info 전용 토큰을 짧게(10분) 별도 발급하는
"임시 다리"가 있었으나 제거됨). 상세 배경은
backend_app/auth/README_employee_auth.md 참고.
"""
import os

EMP_EMAIL_VERIFICATION_TTL_MINUTES = 5

# 2-4. 본인인증용 이메일 발송 계정 (FAQ 기능의 Gmail 계정과 별개).
LOGIN_SMTP_HOST = os.getenv("LOGIN_SMTP_HOST", "smtp.gmail.com")
LOGIN_SMTP_PORT = int(os.getenv("LOGIN_SMTP_PORT", "587"))
LOGIN_SMTP_USERNAME = os.getenv("LOGIN_SMTP_USERNAME", "")
LOGIN_SMTP_APP_PASSWORD = os.getenv("LOGIN_SMTP_APP_PASSWORD", "")
LOGIN_MAIL_FROM = os.getenv("LOGIN_MAIL_FROM", LOGIN_SMTP_USERNAME)
LOGIN_MAIL_ENABLED = bool(LOGIN_SMTP_USERNAME and LOGIN_SMTP_APP_PASSWORD)
