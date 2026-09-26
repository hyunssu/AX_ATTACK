CREATE TABLE IF NOT EXISTS category_favorites (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL,
    category_name TEXT NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(username, category_name)
);

CREATE INDEX IF NOT EXISTS category_favorites_username_idx
    ON category_favorites (username);
