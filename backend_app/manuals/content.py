"""Keep manual versions and displayed content in the selected chunk-table scope."""
from sqlalchemy import text

from db_tables import MANUAL_CHUNK_TABLE_VERSION, MANUAL_PARENT_CHUNKS, MANUALS, MANUAL_VERSIONS

_SCOPE_KEY = "_manual_chunk_table_version"


def public_version_content(blocks: list) -> list:
    return [
        {key: value for key, value in block.items() if key != _SCOPE_KEY}
        if isinstance(block, dict) else block
        for block in blocks
    ]


def stored_version_content(blocks: list) -> list:
    if MANUAL_CHUNK_TABLE_VERSION != "v2":
        return blocks
    content = public_version_content(blocks)
    if not content:
        content = [{"type": "paragraph", "content": []}]
    # Drafts have no search chunks until deployment; keep their scope in existing JSON.
    content[0] = dict(content[0], **{_SCOPE_KEY: "v2"})
    return content


def indexed_version_sql(alias: str) -> str:
    if MANUAL_CHUNK_TABLE_VERSION != "v2":
        return "TRUE"
    return f"""EXISTS (
        SELECT 1 FROM {MANUAL_PARENT_CHUNKS} scope_chunk
        WHERE scope_chunk.version_id = {alias}.id
          AND scope_chunk.manual_id = {alias}.manual_id
    )"""


def active_version_sql(alias: str) -> str:
    if MANUAL_CHUNK_TABLE_VERSION != "v2":
        return "TRUE"
    return f"""(
        {indexed_version_sql(alias)}
        OR {alias}.content_json -> 0 ->> '{_SCOPE_KEY}' = 'v2'
    )"""


def active_manual_sql(alias: str) -> str:
    if MANUAL_CHUNK_TABLE_VERSION != "v2":
        return "TRUE"
    return f"""EXISTS (
        SELECT 1 FROM {MANUAL_VERSIONS} scope_version
        WHERE scope_version.manual_id = {alias}.id
          AND {active_version_sql('scope_version')}
    )"""


def read_version_chunks(conn, manual_id: int, version_id: int, limit: int | None = None):
    limit_clause = "LIMIT :limit" if limit is not None else ""
    return conn.execute(text(f"""
        SELECT c.chunk_index, c.section_title, c.content
        FROM {MANUAL_PARENT_CHUNKS} c JOIN {MANUALS} m ON m.id = c.manual_id
        WHERE c.manual_id = :mid AND c.version_id = :vid AND m.deleted_at IS NULL
        ORDER BY c.chunk_index
        {limit_clause}
    """), {"mid": manual_id, "vid": version_id, "limit": limit}).mappings().all()
