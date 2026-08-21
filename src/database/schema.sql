-- Users table
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Links table
CREATE TABLE IF NOT EXISTS links (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  platform VARCHAR(50) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  error_count INTEGER DEFAULT 0,
  last_parsed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT check_platform CHECK (platform IN ('kufar', 'onliner', 'av', 'realt'))
);

CREATE INDEX IF NOT EXISTS idx_links_user_id ON links(user_id);
CREATE INDEX IF NOT EXISTS idx_links_active ON links(is_active) WHERE is_active = true;

-- Ads table
CREATE TABLE IF NOT EXISTS ads (
  id SERIAL PRIMARY KEY,
  link_id INTEGER REFERENCES links(id) ON DELETE CASCADE,
  external_id VARCHAR(255) NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  price VARCHAR(100),
  image_url TEXT,
  ad_url TEXT NOT NULL,
  location TEXT,
  address TEXT,
  published_at TIMESTAMP,
  updated_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT ads_external_id_link_id_unique UNIQUE (external_id, link_id)
);

CREATE INDEX IF NOT EXISTS idx_ads_link_id ON ads(link_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ads_external_id_unique ON ads(external_id, link_id);
CREATE INDEX IF NOT EXISTS idx_ads_created_at ON ads(created_at);

-- Migration for existing databases: change UNIQUE constraint on external_id to composite (external_id, link_id)
-- This allows the same ad to be tracked across different user links
DO $$
BEGIN
  -- Drop old single-column unique constraint if it exists
  IF EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'ads_external_id_key'
  ) THEN
    ALTER TABLE ads DROP CONSTRAINT ads_external_id_key;
  END IF;
  
  -- Add new composite unique constraint if it doesn't exist yet
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'ads_external_id_link_id_unique'
  ) THEN
    ALTER TABLE ads ADD CONSTRAINT ads_external_id_link_id_unique UNIQUE (external_id, link_id);
  END IF;
END
$$;

-- ============================================
-- Price history tracking
-- ============================================
CREATE TABLE IF NOT EXISTS price_history (
  id SERIAL PRIMARY KEY,
  ad_id INTEGER REFERENCES ads(id) ON DELETE CASCADE,
  old_price VARCHAR(100),
  new_price VARCHAR(100),
  price_change_percent DECIMAL(5,2),
  notified_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_history_ad_id ON price_history(ad_id);
CREATE INDEX IF NOT EXISTS idx_price_history_notified ON price_history(notified_at) WHERE notified_at IS NULL;

-- Уникальный индекс: одно снижение (ad_id, old_price -> new_price) фиксируется только один раз.
-- Это страховка от повторных уведомлений на уровне БД (в т.ч. при параллельной обработке ссылок).
-- Сначала удаляем дубликаты, наплёжённые старой версией бота, иначе CREATE UNIQUE INDEX упадёт.
DELETE FROM price_history a
USING price_history b
WHERE a.id > b.id
  AND a.ad_id = b.ad_id
  AND a.old_price = b.old_price
  AND a.new_price = b.new_price;

CREATE UNIQUE INDEX IF NOT EXISTS idx_price_history_unique_drop
  ON price_history(ad_id, old_price, new_price);

-- Колонка для дедупликации снижений цены на уровне самого объявления,
-- а не его записи в ads. Одна и та же страница поиска может быть добавлена
-- несколько раз (и даже разными пользователями) — у каждой ссылки своя запись
-- в ads со своим id, но external_id объявления один. Дедуп по external_id
-- гарантирует, что одно снижение уведомляется ровно один раз во все каналы/ЛС.
ALTER TABLE price_history ADD COLUMN IF NOT EXISTS external_id VARCHAR(255);

-- Чистим дубликаты по external_id, иначе уникальный индекс не создастся.
DELETE FROM price_history a
USING price_history b
WHERE a.id > b.id
  AND a.external_id IS NOT NULL
  AND b.external_id IS NOT NULL
  AND a.external_id = b.external_id
  AND a.old_price = b.old_price
  AND a.new_price = b.new_price;

CREATE UNIQUE INDEX IF NOT EXISTS idx_price_history_unique_drop_external
  ON price_history(external_id, old_price, new_price)
  WHERE external_id IS NOT NULL;

-- ============================================
-- Telegram channel subscriptions
-- ============================================
CREATE TABLE IF NOT EXISTS channel_subscriptions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  channel_id BIGINT NOT NULL,
  channel_username VARCHAR(255),
  channel_title VARCHAR(500),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT unique_channel_per_user UNIQUE (user_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_subscriptions_user_id ON channel_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_channel_subscriptions_active ON channel_subscriptions(is_active) WHERE is_active = true;
