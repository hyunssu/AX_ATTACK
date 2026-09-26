"""회원가입 화면의 select box용 메타/조직 정보 조회.

team_info는 (본국행원여부/회사/팀/파트) 조합별로 한 행씩 저장되어 있으므로,
화면의 4단 계층 select(본국행원여부 -> 회사 -> 팀 -> 파트)는 프론트엔드에서
이 목록을 그대로 받아 domestic_code/company_code/team_code로 순차
필터링해 구성한다.
"""
from sqlalchemy import text

from db import engine

from auth.emp_tables import COUNTRIES_INFO, LANGUAGE_INFO, PERMISSION_INFO, POSITION_INFO, TEAM_INFO


def list_teams():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT org_code, domestic_code, company_code, company_name_ko, company_name_en, "
                "team_code, team_name_ko, team_name_en, "
                "part_code, part_name_ko, part_name_en "
                f"FROM {TEAM_INFO} ORDER BY org_code"
            )
        ).mappings().all()
    return [dict(row) for row in rows]


def list_positions():
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT code, name_ko, name_en FROM {POSITION_INFO} ORDER BY code")
        ).mappings().all()
    return [dict(row) for row in rows]


def list_permissions():
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT code, name_ko, name_en FROM {PERMISSION_INFO} ORDER BY code")
        ).mappings().all()
    return [dict(row) for row in rows]


def list_languages():
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT code, name_ko, name_en FROM {LANGUAGE_INFO} ORDER BY code")
        ).mappings().all()
    return [dict(row) for row in rows]


def list_countries():
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT code, name_ko, name_en FROM {COUNTRIES_INFO} ORDER BY code")
        ).mappings().all()
    return [dict(row) for row in rows]
