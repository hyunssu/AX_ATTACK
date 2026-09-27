"""회원가입 이메일 인증번호 발송.

기존 backend_app/faq/mailer.py, config.py의 FAQ_SMTP_*는 건드리지 않는다.
본인인증 전용 Gmail 계정(LOGIN_SMTP_*, backend_app/auth/emp_config.py)을
별도로 사용한다.
"""
import smtplib
from email.mime.text import MIMEText

from auth.emp_config import (
    LOGIN_MAIL_ENABLED,
    LOGIN_MAIL_FROM,
    LOGIN_SMTP_APP_PASSWORD,
    LOGIN_SMTP_HOST,
    LOGIN_SMTP_PORT,
    LOGIN_SMTP_USERNAME,
)


def send_verification_email(to_email: str, code: str) -> None:
    """LOGIN_MAIL_ENABLED가 꺼져 있으면(계정 미설정) 발송을 건너뛴다."""
    if not LOGIN_MAIL_ENABLED:
        return

    message = MIMEText(f"인증번호: {code}\n5분 이내에 입력해 주세요.")
    message["Subject"] = "[Aither] 이메일 인증번호"
    message["From"] = LOGIN_MAIL_FROM
    message["To"] = to_email

    with smtplib.SMTP(LOGIN_SMTP_HOST, LOGIN_SMTP_PORT) as server:
        server.starttls()
        server.login(LOGIN_SMTP_USERNAME, LOGIN_SMTP_APP_PASSWORD)
        server.sendmail(LOGIN_MAIL_FROM, [to_email], message.as_string())
