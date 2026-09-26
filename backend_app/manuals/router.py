import json
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text

from auth.service import get_current_user
from config import DEFAULT_ADMIN_USER
from db import engine
from manuals import jobs
from manuals.classification import build_subs_section, classify_sections, reclassify_section_strong, suggest_sub_from_title
from manuals.indexing import index_document, index_section
from manuals.permissions import can_edit_category, require_category_edit, require_manual_edit
from manuals.splitting import split_into_major_sections
from storage import upload_file

router = APIRouter(prefix="/api/manuals", tags=["manuals"])


def _fetch_subs_by_cat() -> dict[str, list[str]]:
    """manual_trails 테이블에서 카테고리별 소분류 목록을 반환한다."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT category, name FROM manual_trails ORDER BY category, created_at")
        ).mappings().all()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row["category"], []).append(row["name"])
    return result

ALLOWED_EXTENSIONS = (".md",)


def _save_temp_file(file_bytes: bytes, filename: str) -> str:
    tmp_path = f"/tmp/{uuid.uuid4()}_{filename}"
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)
    return tmp_path


def _validate_extension(filename: str):
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Markdown(.md) 파일만 업로드할 수 있습니다.")


def _run_indexing_job(tmp_path: str, manual_id: int, version_id: int, job_id: int):
    try:
        index_document(tmp_path, manual_id, version_id, job_id=job_id)
    finally:
        os.remove(tmp_path)


def _text_to_content_blocks(text: str) -> list:
    """섹션 텍스트를 BlockNote 단락 블록 배열로 변환한다."""
    blocks = []
    for para in text.strip().split('\n\n'):
        for line in para.split('\n'):
            line = line.strip()
            if line:
                blocks.append({
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line, "styles": {}}],
                })
    return blocks


@router.post("/preview-sections")
async def preview_manual_sections(
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    _validate_extension(file.filename)
    file_bytes = await file.read()
    tmp_path = _save_temp_file(file_bytes, file.filename)
    try:
        sections = split_into_major_sections(tmp_path)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일 인코딩을 읽을 수 없습니다. UTF-8 텍스트 파일인지 확인해 주세요.")
    finally:
        os.remove(tmp_path)
    source_type = "pdf" if file.filename.lower().endswith(".pdf") else "md"
    return {"sections": sections, "section_count": len(sections), "source_type": source_type}


class ConfirmSectionInput(BaseModel):
    title: str
    content: str
    categories: list[str] = Field(min_length=1)
    sub_category: str | None = None
    include: bool = True


class ConfirmSectionsRequest(BaseModel):
    file_name: str
    file_url: str
    source_type: str
    sections: list[ConfirmSectionInput]
    lang_c: str = "ko"
    deploy: bool = True


@router.post("/analyze")
async def analyze_manual(
    file: UploadFile = File(...),
    context_category: str = Form(...),
    username: str = Depends(get_current_user),
):
    require_category_edit(username, context_category)
    _validate_extension(file.filename)
    file_bytes = await file.read()
    source_type = "pdf" if file.filename.lower().endswith(".pdf") else "md"

    file_url, _ = upload_file(file_bytes, file.filename, file.content_type)
    tmp_path = _save_temp_file(file_bytes, file.filename)
    try:
        sections = split_into_major_sections(tmp_path)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="파일 인코딩을 읽을 수 없습니다. UTF-8 텍스트 파일인지 확인해 주세요.")
    finally:
        os.remove(tmp_path)

    subs = _fetch_subs_by_cat().get(context_category, [])
    classified = classify_sections(sections, category=context_category, subs=subs)

    return {
        "file_name": file.filename,
        "file_url": file_url,
        "source_type": source_type,
        "sections": classified,
        "section_count": len(classified),
    }


class ReclassifySectionRequest(BaseModel):
    category: str
    title: str
    content: str


@router.post("/reclassify-section")
async def reclassify_section(
    req: ReclassifySectionRequest,
    username: str = Depends(get_current_user),
):
    require_category_edit(username, req.category)
    subs = _fetch_subs_by_cat().get(req.category, [])
    subs_section = build_subs_section(subs)
    in_category, sub_category, needs_review = reclassify_section_strong(req.category, req.title, req.content, subs_section)
    return {"include": in_category, "sub_category": sub_category, "needs_review": needs_review}


@router.post("/confirm")
async def confirm_manual_sections(
    req: ConfirmSectionsRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(get_current_user),
):
    included = [s for s in req.sections if s.include]
    if not included:
        raise HTTPException(status_code=400, detail="포함할 섹션이 하나도 없습니다.")
    for section in included:
        require_category_edit(username, section.categories[0] if section.categories else None)

    created = []
    with engine.begin() as conn:
        for section in included:
            manual_id = conn.execute(
                text("""
                    INSERT INTO manuals (title, categories, sub_category, created_by, lang_c)
                    VALUES (:title, :categories, :sub_category, :created_by, :lang_c)
                    RETURNING id
                """),
                {
                    "title": section.title,
                    "categories": section.categories,
                    "sub_category": section.sub_category,
                    "created_by": username,
                    "lang_c": req.lang_c,
                }
            ).scalar_one()
            if req.deploy:
                version_id = conn.execute(
                    text("""
                        INSERT INTO manual_versions (manual_id, version_no, file_name, file_url, source_type, index_step)
                        VALUES (:manual_id, 1, :file_name, :file_url, :source_type, 'converting')
                        RETURNING id
                    """),
                    {"manual_id": manual_id, "file_name": req.file_name, "file_url": req.file_url, "source_type": req.source_type}
                ).scalar_one()
            else:
                content_blocks = _text_to_content_blocks(section.content)
                version_id = conn.execute(
                    text("""
                        INSERT INTO manual_versions (manual_id, version_no, file_name, file_url, source_type, index_step, content_json)
                        VALUES (:manual_id, 1, :file_name, :file_url, :source_type, 'draft', CAST(:content_json AS jsonb))
                        RETURNING id
                    """),
                    {
                        "manual_id": manual_id,
                        "file_name": req.file_name,
                        "file_url": req.file_url,
                        "source_type": req.source_type,
                        "content_json": json.dumps(content_blocks),
                    }
                ).scalar_one()
            created.append((manual_id, version_id))

    # 새 소분류는 trail로 자동 등록
    with engine.begin() as conn:
        for section in included:
            if section.sub_category and section.categories:
                conn.execute(
                    text("""
                        INSERT INTO manual_trails (category, name, created_by)
                        VALUES (:cat, :name, :user)
                        ON CONFLICT (category, name) DO NOTHING
                    """),
                    {"cat": section.categories[0], "name": section.sub_category, "user": username},
                )

    # jobs.create_job() opens its own transaction, so it must run after the block above
    # commits — otherwise it can't see the manuals/manual_versions rows just inserted.
    results = []
    if req.deploy:
        for section, (manual_id, version_id) in zip(included, created):
            job_id = jobs.create_job(manual_id, version_id)
            results.append({"manual_id": manual_id, "version_id": version_id, "job_id": job_id, "title": section.title})
        for section, result in zip(included, results):
            background_tasks.add_task(
                index_section, section.title, section.content, result["manual_id"], result["version_id"], result["job_id"]
            )
    else:
        for section, (manual_id, version_id) in zip(included, created):
            results.append({"manual_id": manual_id, "version_id": version_id, "job_id": None, "title": section.title})

    return {"results": results}


_FALLBACK_CATEGORY_TEAMS = {
    "여신": ("1113", "글로벌개발부"),
    "수신": ("1112", "글로벌개발부"),
    "외환": ("1114", "글로벌개발부"),
    "자금": ("1115", "글로벌개발부"),
    "카드": (None, None),
    "고객": ("1111", "글로벌개발부"),
    "기타": (None, None),
}


@router.get("/categories")
def list_categories(username: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    text("""
                        SELECT c.name, c.name_en, c.color, c.color_light, c.sort_order,
                               c.org_code, t.team_name_ko, t.part_name_ko
                        FROM manual_categories c
                        LEFT JOIN team_info t ON t.org_code = c.org_code
                        ORDER BY c.sort_order, c.name
                    """)
                ).mappings().all()
            ]
    except Exception:
        rows = [
            {
                "name": n, "name_en": e, "color": c, "color_light": l, "sort_order": i + 1,
                "org_code": _FALLBACK_CATEGORY_TEAMS.get(n, (None, None))[0],
                "team_name_ko": _FALLBACK_CATEGORY_TEAMS.get(n, (None, None))[1],
                "part_name_ko": n,
            }
            for i, (n, e, c, l) in enumerate([
                ("여신", "Credit",   "#4a7fcb", "#daeaf9"),
                ("수신", "Deposit",  "#4fad8a", "#cceee0"),
                ("외환", "FX",       "#8b72d4", "#e2dcf8"),
                ("자금", "Treasury", "#d4843f", "#f8e4ca"),
                ("카드", "Card",     "#d45e6e", "#f9d5d8"),
                ("고객", "Customer", "#5b9fd4", "#cce2f8"),
                ("기타", "Others",   "#8a9bb0", "#d8dee4"),
            ])
        ]
    for row in rows:
        row["can_edit"] = can_edit_category(username, row["name"])
    return rows


@router.get("/terms")
def list_terms(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, term, aliases, description, created_by, created_at FROM manual_terms ORDER BY created_at DESC")
        ).mappings().all()
    return [dict(r) for r in rows]


class CreateTermRequest(BaseModel):
    term: str
    aliases: list[str] = []
    description: str


@router.post("/terms")
def create_term(req: CreateTermRequest, username: str = Depends(get_current_user)):
    term = req.term.strip()
    aliases = [a.strip() for a in req.aliases if a.strip()]
    if not term or not req.description.strip():
        raise HTTPException(status_code=400, detail="term과 description은 필수입니다.")
    with engine.begin() as conn:
        try:
            row = conn.execute(
                text("""
                    INSERT INTO manual_terms (term, aliases, description, created_by)
                    VALUES (:term, :aliases, :desc, :user)
                    ON CONFLICT (term) DO UPDATE
                      SET aliases = :aliases, description = :desc
                    RETURNING id, term, aliases, description, created_by, created_at
                """),
                {"term": term, "aliases": aliases, "desc": req.description.strip(), "user": username},
            ).mappings().first()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return dict(row)


@router.delete("/terms/{term_id}")
def delete_term(term_id: int, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM manual_terms WHERE id = :id"), {"id": term_id})
    return {"ok": True}


@router.get("/categories/favorites")
def list_category_favorites(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT category_name FROM category_favorites WHERE username = :u"),
            {"u": username},
        ).fetchall()
    return [r[0] for r in rows]


@router.post("/categories/{name}/favorite")
def add_category_favorite(name: str, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO category_favorites (username, category_name) VALUES (:u, :n) ON CONFLICT DO NOTHING"),
            {"u": username, "n": name},
        )
    return {"ok": True}


@router.delete("/categories/{name}/favorite")
def remove_category_favorite(name: str, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM category_favorites WHERE username = :u AND category_name = :n"),
            {"u": username, "n": name},
        )
    return {"ok": True}


@router.get("/favorites")
def list_favorites(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT manual_id FROM manual_favorites WHERE username = :u"),
            {"u": username},
        ).fetchall()
    return [r[0] for r in rows]


@router.post("/{manual_id}/favorite")
def add_favorite(manual_id: int, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO manual_favorites (username, manual_id) VALUES (:u, :m) ON CONFLICT DO NOTHING"),
            {"u": username, "m": manual_id},
        )
    return {"ok": True}


@router.delete("/{manual_id}/favorite")
def remove_favorite(manual_id: int, username: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM manual_favorites WHERE username = :u AND manual_id = :m"),
            {"u": username, "m": manual_id},
        )
    return {"ok": True}


class CreateTrailRequest(BaseModel):
    category: str
    name: str
    name_en: str | None = None


@router.get("/trails")
def list_trails(category: str, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name, name_en FROM manual_trails WHERE category = :cat ORDER BY created_at"),
            {"cat": category},
        ).mappings().all()
    return [dict(r) for r in rows]


@router.post("/trails")
def create_trail(req: CreateTrailRequest, username: str = Depends(get_current_user)):
    require_category_edit(username, req.category)
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="트레일 이름을 입력해 주세요.")
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO manual_trails (category, name, name_en, created_by)
                VALUES (:cat, :name, :name_en, :user)
                ON CONFLICT (category, name) DO NOTHING
            """),
            {"cat": req.category, "name": req.name, "name_en": req.name_en, "user": username},
        )
    return {"ok": True}


class DeleteTrailRequest(BaseModel):
    category: str
    name: str


@router.delete("/trails")
def delete_trail(req: DeleteTrailRequest, username: str = Depends(get_current_user)):
    require_category_edit(username, req.category)
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM manual_trails WHERE category = :cat AND name = :name"),
            {"cat": req.category, "name": req.name},
        )
        conn.execute(
            text("""
                UPDATE manuals SET sub_category = NULL
                WHERE :cat = ANY(categories) AND sub_category = :name
            """),
            {"cat": req.category, "name": req.name},
        )
    return {"ok": True}


class RenameTrailRequest(BaseModel):
    category: str
    old_name: str
    new_name: str
    new_name_en: str | None = None


@router.patch("/trails")
def rename_trail(req: RenameTrailRequest, username: str = Depends(get_current_user)):
    require_category_edit(username, req.category)
    new = req.new_name.strip()
    if not new:
        raise HTTPException(status_code=400, detail="새 이름을 입력해 주세요.")
    if new == req.old_name:
        return {"ok": True}
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE manual_trails SET name = :new, name_en = :name_en
                WHERE category = :cat AND name = :old
            """),
            {"new": new, "name_en": req.new_name_en, "cat": req.category, "old": req.old_name},
        )
        conn.execute(
            text("""
                UPDATE manuals SET sub_category = :new
                WHERE :cat = ANY(categories) AND sub_category = :old
            """),
            {"new": new, "cat": req.category, "old": req.old_name},
        )
    return {"ok": True}


class QuickCreateRequest(BaseModel):
    title: str
    categories: list[str]
    sub_category: str | None = None
    lang_c: str = "ko"


@router.post("/quick-create")
def quick_create_manual(
    req: QuickCreateRequest,
    username: str = Depends(get_current_user),
):
    """파일 없이 빈 매뉴얼을 만든다. AI가 제목을 보고 소분류를 추천하며, 현재 sub_category와 다를 때만 배지로 표시된다."""
    category = req.categories[0] if req.categories else None
    require_category_edit(username, category)
    subs_by_cat = _fetch_subs_by_cat()
    ai_sub = suggest_sub_from_title(req.title, category, subs_by_cat.get(category, [])) if category else None
    # 현재 지정된 소분류와 동일하면 배지 불필요
    ai_suggested_sub = ai_sub if ai_sub and ai_sub != req.sub_category else None

    with engine.begin() as conn:
        manual_id = conn.execute(
            text("""
                INSERT INTO manuals (title, categories, sub_category, created_by, ai_suggested_sub, lang_c)
                VALUES (:title, :categories, :sub_category, :created_by, :ai_suggested_sub, :lang_c)
                RETURNING id
            """),
            {
                "title": req.title,
                "categories": req.categories,
                "sub_category": req.sub_category,
                "created_by": username,
                "ai_suggested_sub": ai_suggested_sub,
                "lang_c": req.lang_c,
            },
        ).scalar_one()
        version_id = conn.execute(
            text("""
                INSERT INTO manual_versions (manual_id, version_no, file_name, file_url, index_step)
                VALUES (:manual_id, 1, '', '', 'draft')
                RETURNING id
            """),
            {"manual_id": manual_id},
        ).scalar_one()
    return {"manual_id": manual_id, "version_id": version_id, "ai_suggested_sub": ai_suggested_sub}


class SetSubCategoryRequest(BaseModel):
    sub_category: str | None


@router.put("/{manual_id}/sub-category")
def set_sub_category(manual_id: int, req: SetSubCategoryRequest, username: str = Depends(get_current_user)):
    """소분류를 변경하고 AI 추천 배지를 제거한다 (수락)."""
    require_manual_edit(username, manual_id)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE manuals SET sub_category = :sub, ai_suggested_sub = NULL WHERE id = :id"),
            {"sub": req.sub_category, "id": manual_id},
        )
    return {"ok": True}


@router.delete("/{manual_id}/ai-suggested-sub")
def dismiss_ai_suggestion(manual_id: int, username: str = Depends(get_current_user)):
    """AI 추천 배지만 제거한다 (거절). sub_category는 변경되지 않는다."""
    require_manual_edit(username, manual_id)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE manuals SET ai_suggested_sub = NULL WHERE id = :id"),
            {"id": manual_id},
        )
    return {"ok": True}


@router.post("")
async def create_manual(
    background_tasks: BackgroundTasks,
    title: str,
    file: UploadFile = File(...),
    deploy: bool = True,
    lang_c: str = "ko",
    username: str = Depends(get_current_user),
):
    _validate_extension(file.filename)
    file_bytes = await file.read()
    file_url, storage_path = upload_file(file_bytes, file.filename, file.content_type)

    index_step = "converting" if deploy else "draft"
    with engine.begin() as conn:
        manual_id = conn.execute(
            text("INSERT INTO manuals (title, created_by, lang_c) VALUES (:title, :created_by, :lang_c) RETURNING id"),
            {"title": title, "created_by": username, "lang_c": lang_c}
        ).scalar_one()
        version_id = conn.execute(
            text("""
                INSERT INTO manual_versions (manual_id, version_no, file_name, file_url, storage_path, index_step)
                VALUES (:manual_id, 1, :file_name, :file_url, :storage_path, :index_step)
                RETURNING id
            """),
            {
                "manual_id": manual_id,
                "file_name": file.filename,
                "file_url": file_url,
                "storage_path": storage_path,
                "index_step": index_step,
            }
        ).scalar_one()

    if deploy:
        tmp_path = _save_temp_file(file_bytes, file.filename)
        job_id = jobs.create_job(manual_id, version_id)
        background_tasks.add_task(_run_indexing_job, tmp_path, manual_id, version_id, job_id)
        return {"manual_id": manual_id, "version_id": version_id, "file_url": file_url, "job_id": job_id}

    return {"manual_id": manual_id, "version_id": version_id, "file_url": file_url, "job_id": None}


@router.post("/{manual_id}/versions")
async def create_manual_version(
    manual_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    deploy: bool = True,
    username: str = Depends(get_current_user),
):
    _validate_extension(file.filename)
    require_manual_edit(username, manual_id)
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT id FROM manuals WHERE id = :id"), {"id": manual_id}).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Manual not found")
        next_version = conn.execute(
            text("SELECT COALESCE(MAX(version_no), 0) + 1 FROM manual_versions WHERE manual_id = :id"),
            {"id": manual_id}
        ).scalar_one()

    file_bytes = await file.read()
    file_url, storage_path = upload_file(file_bytes, file.filename, file.content_type)
    index_step = "converting" if deploy else "draft"

    with engine.begin() as conn:
        version_id = conn.execute(
            text("""
                INSERT INTO manual_versions (manual_id, version_no, file_name, file_url, storage_path, index_step)
                VALUES (:manual_id, :version_no, :file_name, :file_url, :storage_path, :index_step)
                RETURNING id
            """),
            {
                "manual_id": manual_id,
                "version_no": next_version,
                "file_name": file.filename,
                "file_url": file_url,
                "storage_path": storage_path,
                "index_step": index_step,
            }
        ).scalar_one()

    if deploy:
        tmp_path = _save_temp_file(file_bytes, file.filename)
        job_id = jobs.create_job(manual_id, version_id)
        background_tasks.add_task(_run_indexing_job, tmp_path, manual_id, version_id, job_id)
        return {"manual_id": manual_id, "version_id": version_id, "version_no": next_version, "file_url": file_url, "job_id": job_id}

    return {"manual_id": manual_id, "version_id": version_id, "version_no": next_version, "file_url": file_url, "job_id": None}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: int, username: str = Depends(get_current_user)):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"step": job["step"], "error_message": job["error_message"]}


_LIST_MANUALS_SQL = """
    SELECT
        m.id, m.title, m.categories, m.sub_category, m.ai_suggested_sub,
        m.created_by, m.created_at, m.lang_c,
        m.locked_by, m.locked_at,
        COUNT(mv.id) AS version_count,
        MAX(CASE WHEN mv.index_step = 'done' THEN mv.version_no END) AS latest_done_version_no,
        (
            SELECT mv2.index_step
            FROM manual_versions mv2
            WHERE mv2.manual_id = m.id AND mv2.index_step != 'done'
            ORDER BY mv2.version_no DESC
            LIMIT 1
        ) AS latest_draft_index_step
    FROM manuals m
    LEFT JOIN manual_versions mv ON mv.manual_id = m.id
    {where}
    GROUP BY m.id
    ORDER BY m.id DESC
"""


@router.get("")
def list_manuals(username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        if username == DEFAULT_ADMIN_USER:
            rows = conn.execute(
                text(_LIST_MANUALS_SQL.format(where=""))
            ).mappings().all()
        else:
            rows = conn.execute(
                text(_LIST_MANUALS_SQL.format(where="WHERE m.created_by = :username")),
                {"username": username}
            ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{manual_id}/versions")
def list_versions(manual_id: int, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, version_no, file_name, file_url, index_step, created_at
                FROM manual_versions WHERE manual_id = :id ORDER BY version_no DESC
            """),
            {"id": manual_id}
        ).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{manual_id}/lock")
def lock_manual(manual_id: int, username: str = Depends(get_current_user)):
    require_manual_edit(username, manual_id)
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT locked_by FROM manuals WHERE id = :id"),
            {"id": manual_id},
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="매뉴얼을 찾을 수 없습니다.")
        if row[0] and row[0] != username:
            raise HTTPException(status_code=409, detail=f"이미 {row[0]}님이 편집 중입니다.")
        conn.execute(
            text("UPDATE manuals SET locked_by = :u, locked_at = now() WHERE id = :id"),
            {"u": username, "id": manual_id},
        )
    return {"locked_by": username}


@router.delete("/{manual_id}/lock")
def unlock_manual(manual_id: int, username: str = Depends(get_current_user)):
    require_manual_edit(username, manual_id)
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT locked_by FROM manuals WHERE id = :id"),
            {"id": manual_id},
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="매뉴얼을 찾을 수 없습니다.")
        if row[0] and row[0] != username and username != DEFAULT_ADMIN_USER:
            raise HTTPException(status_code=403, detail="잠금을 해제할 권한이 없습니다.")
        conn.execute(
            text("UPDATE manuals SET locked_by = NULL, locked_at = NULL WHERE id = :id"),
            {"id": manual_id},
        )
    return {"locked_by": None}


@router.delete("/{manual_id}")
def delete_manual(manual_id: int, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT created_by FROM manuals WHERE id = :id"),
            {"id": manual_id},
        ).first()
    if not row:
        raise HTTPException(status_code=404, detail="매뉴얼을 찾을 수 없습니다.")
    if username != DEFAULT_ADMIN_USER and row[0] != username:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM manuals WHERE id = :id"), {"id": manual_id})
    return {"ok": True}


@router.get("/{manual_id}/versions/{version_id}/content")
def get_version_content(manual_id: int, version_id: int, username: str = Depends(get_current_user)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT chunk_index, section_title, content
                FROM manual_chunks_khs
                WHERE manual_id = :manual_id AND version_id = :version_id
                ORDER BY chunk_index
            """),
            {"manual_id": manual_id, "version_id": version_id}
        ).mappings().all()
    return {"chunks": [dict(r) for r in rows]}
