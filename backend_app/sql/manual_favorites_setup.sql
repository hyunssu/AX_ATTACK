CREATE TABLE IF NOT EXISTS manual_favorites (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL,
    manual_id  INTEGER NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(username, manual_id)
);

CREATE INDEX IF NOT EXISTS manual_favorites_username_idx
    ON manual_favorites (username);
