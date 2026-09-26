CREATE TABLE IF NOT EXISTS manual_terms (
    id          SERIAL PRIMARY KEY,
    term        TEXT        NOT NULL,
    aliases     TEXT[]      NOT NULL DEFAULT '{}',
    description TEXT        NOT NULL,
    created_by  TEXT        NOT NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT now(),
    UNIQUE(term)
);

CREATE INDEX IF NOT EXISTS manual_terms_term_lower_idx ON manual_terms (lower(term));
