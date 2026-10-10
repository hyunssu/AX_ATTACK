"""users의 배열 프로필을 정규화하고 누락된 값은 users_kyj에서 보완한다."""
import csv
import json
from sqlalchemy import text
from db import engine
from db_tables import USERS, LEGACY_USERS


def normalize_list(value):
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    value = str(value).strip()
    try:
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return normalize_list(decoded)
    except (ValueError, TypeError):
        pass
    if value.startswith('{') and value.endswith('}'):
        value = value[1:-1]
    return [item.strip() for item in next(csv.reader([value])) if item.strip()]


def read_profiles(username=None):
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT to_jsonb(u) AS profile FROM {USERS} u WHERE (CAST(:username AS text) IS NULL OR u.username = :username)"), {"username": username}).mappings().all()
        legacy_exists = conn.execute(text("SELECT to_regclass(:table)"), {"table": f"public.{LEGACY_USERS}"}).scalar()
        legacy = conn.execute(text(f"SELECT to_jsonb(u) AS profile FROM {LEGACY_USERS} u WHERE (CAST(:username AS text) IS NULL OR u.username = :username)"), {"username": username}).mappings().all() if legacy_exists else []
    backups = {row['profile']['username']: row['profile'] for row in legacy}
    result = []
    for row in rows:
        profile = dict(row['profile'])
        backup = backups.get(profile['username'], {})
        for key in ('countries', 'expertise_keywords'):
            profile[key] = normalize_list(profile.get(key)) or normalize_list(backup.get(key))
        result.append(profile)
    return result
