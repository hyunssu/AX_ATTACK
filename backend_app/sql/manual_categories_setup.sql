-- 분류 마스터 테이블 — DBeaver에서 직접 실행
CREATE TABLE IF NOT EXISTS manual_categories (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    name_en    TEXT NOT NULL DEFAULT '',
    color      TEXT NOT NULL DEFAULT '#8a9bb0',
    color_light TEXT NOT NULL DEFAULT '#d8dee4',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO manual_categories (name, name_en, color, color_light, sort_order) VALUES
  ('여신', 'Credit',   '#4a7fcb', '#daeaf9', 1),
  ('수신', 'Deposit',  '#4fad8a', '#cceee0', 2),
  ('외환', 'FX',       '#8b72d4', '#e2dcf8', 3),
  ('자금', 'Treasury', '#d4843f', '#f8e4ca', 4),
  ('카드', 'Card',     '#d45e6e', '#f9d5d8', 5),
  ('고객', 'Customer', '#5b9fd4', '#cce2f8', 6),
  ('기타', 'Others',   '#8a9bb0', '#d8dee4', 7)
ON CONFLICT (name) DO NOTHING;
