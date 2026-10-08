# Manual Chunk Tables V2

Both local and production Docker Compose set `MANUAL_CHUNK_TABLE_VERSION=v2`.
With no setting, the backend continues to use the original v1 tables.
The production Compose setting is activated by the main branch deployment.

Before switching production, confirm how legacy manuals will be handled.
Manuals without v2 chunks or a v2-scoped draft are hidden, not deleted.
To roll back, set the production backend environment to
`MANUAL_CHUNK_TABLE_VERSION=v1` and recreate the backend container.
Switching this setting does not copy, reindex or delete existing chunks.

## Data Flow

- Saving or verifying a draft does not write search chunks.
- Deploying a draft writes `manual_parent_chunks_v2` and `manual_child_chunks_v2`.
- Every v2 child has `lang_c = 'ko'`.
- RAG reads only v2 chunks from the latest completed version indexed in v2.
- Manual lists, trash, version history and displayed content use the v2 scope.
- Versions with v2 parent chunks are visible; legacy-only manuals are hidden.
- New local drafts are also visible before deployment. A private
  `_manual_chunk_table_version: "v2"` key on the first saved content block
  identifies them without adding a table or column. API responses remove this
  key before sending blocks to the editor.
- Empty drafts keep an empty paragraph block so their scope survives saving.
- Original editor/Markdown content comes only from a v2-scoped version;
  reconstructed published content reads only `manual_parent_chunks_v2`.
- No display or search query falls back to legacy chunks, including when v2 is empty.
- A newer legacy version does not replace the local v2 version. New version
  numbers still use the shared maximum to avoid collisions.
- Existing chunks are not copied or automatically reindexed.

## Chunk Rules

Markdown is parsed with markdown-it-py. Screen headings delimit manuals;
headings inside code fences and the document contents list are not screens.
Child prefixes repeat the screen title and detail heading. The major topic is
included in the content and parent heading path, not in an additional column.

Short descriptions stay together. Long prose splits at paragraph or sentence
boundaries. Procedures and field rows remain intact; 300/1500-character sizes
are soft targets rather than reasons to cut a field or word in half.
Each field row becomes one child with the table's column labels on every value.
Embeddings are computed before atomically replacing a version's v2 chunks.

## Shared Database

The local application still uses the configured shared `manuals` and
`manual_versions` tables. Only the chunk tables are isolated. Creating, editing,
deleting or deploying a manual locally changes shared manual metadata.
Use a new test manual instead of editing an existing production manual.

## Verification

Run opt-in backend tests with `RUN_MANUAL_DB_TESTS=1`. Database writes are
rolled back, and embedding/verification calls are mocked. Schema tests use a
temporary schema. The reference document test also needs the repository's
`documents` directory alongside `backend_app` inside the container.
