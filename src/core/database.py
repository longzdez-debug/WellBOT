"""Database layer — async SQLite operations."""

import aiosqlite
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.core.config import config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, connection: aiosqlite.Connection = None):
        self.connection: Optional[aiosqlite.Connection] = connection
        self.db_path = config.DATABASE_PATH

    async def init_db(self):
        """Initialize database connection and create tables."""
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        """Create all required tables."""
        # Users table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                subscription_until TIMESTAMP,
                tariff_plan TEXT DEFAULT 'basic',
                is_admin BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                is_banned BOOLEAN DEFAULT FALSE,
                referrer_id INTEGER,
                language TEXT DEFAULT 'ru',
                last_active_at TIMESTAMP,
                quiet_start TEXT DEFAULT '00',
                quiet_end TEXT DEFAULT '08',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._migrate_users_table()

        # Searches table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                title TEXT,
                url TEXT,
                min_price REAL DEFAULT 0,
                max_price REAL DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                excluded_keywords TEXT,
                price_drop_threshold REAL DEFAULT 0,
                only_photos BOOLEAN DEFAULT FALSE,
                channel_id INTEGER
            )
        """)
        await self._migrate_searches_table()

        # Sent ads table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS sent_ads (
                user_id INTEGER,
                ad_id TEXT,
                search_id INTEGER,
                price REAL DEFAULT 0,
                PRIMARY KEY (user_id, ad_id, search_id)
            )
        """)

        # Weekly stats table
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS weekly_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                search_id INTEGER,
                week_start TEXT,
                total_ads INTEGER DEFAULT 0,
                avg_price REAL DEFAULT 0,
                min_price REAL DEFAULT 0,
                max_price REAL DEFAULT 0,
                UNIQUE(user_id, search_id, week_start)
            )
        """)

        # Badges definitions
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT NOT NULL,
                description TEXT NOT NULL,
                condition TEXT NOT NULL
            )
        """)

        # User badges
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                user_id INTEGER,
                badge_key TEXT,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, badge_key),
                FOREIGN KEY(badge_key) REFERENCES badges(key)
            )
        """)

        # Promocodes
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                days INTEGER NOT NULL,
                max_uses INTEGER DEFAULT -1,
                used_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Promo redemptions
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS promo_redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, code)
            )
        """)

        # Create indexes
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_sent_ads_ad_search ON sent_ads(ad_id, search_id)")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_weekly_stats_user ON weekly_stats(user_id, week_start)")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges(user_id)")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_searches_user_active ON searches(user_id, is_active)")
        await self.connection.execute("CREATE INDEX IF NOT EXISTS idx_users_language ON users(language)")

        # Initialize badges if not exists
        cursor = await self.connection.execute("SELECT COUNT(*) FROM badges")
        row = await cursor.fetchone()
        badge_count = row[0] if row else 0
        
        if badge_count == 0:
            badges_data = [
                ("first_search", "Первый шаг", "🔍", "Создайте свой первый поиск", "total_searches >= 1"),
                ("searcher", "Исследователь", "🗺️", "Создайте 10 поисков", "total_searches >= 10"),
                ("pro_searcher", "Профи поиска", "🎯", "Создайте 50 поисков", "total_searches >= 50"),
                ("first_ad", "Первая находка", "🎉", "Получите первое уведомление", "total_ads >= 1"),
                ("collector", "Коллекционер", "📦", "Получите 100 уведомлений", "total_ads >= 100"),
                ("social", "Коммуникабельный", "🤝", "Пригласите первого друга", "referrals >= 1"),
                ("influencer", "Лидер мнений", "👑", "Пригласите 5 друзей", "referrals >= 5"),
                ("pro_member", "Pro подписчик", "💎", "Оформите подписку Pro", "tariff_plan = 'pro'"),
                ("vip", "VIP клиент", "⭐", "Pro + 200 уведомлений", "tariff_plan = 'pro' AND total_ads >= 200"),
            ]
            for key, name, icon, desc, condition in badges_data:
                await self.connection.execute(
                    "INSERT INTO badges (key, name, icon, description, condition) VALUES (?, ?, ?, ?, ?)",
                    (key, name, icon, desc, condition)
                )

        await self.connection.commit()

    async def _migrate_users_table(self):
        """Add columns that may not exist in older databases."""
        cursor = await self.connection.execute("PRAGMA table_info(users)")
        rows = await cursor.fetchall()
        columns = [row[1] for row in rows]
        
        for col, definition in [
            ("tariff_plan", "TEXT DEFAULT 'basic'"),
            ("is_banned", "BOOLEAN DEFAULT FALSE"),
            ("referrer_id", "INTEGER"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("language", "TEXT DEFAULT 'ru'"),
            ("last_active_at", "TIMESTAMP"),
            ("quiet_start", "TEXT DEFAULT '00'"),
            ("quiet_end", "TEXT DEFAULT '08'"),
        ]:
            if col not in columns:
                await self.connection.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        await self.connection.commit()

    async def _migrate_searches_table(self):
        """Add columns that may not exist in older databases."""
        cursor = await self.connection.execute("PRAGMA table_info(searches)")
        rows = await cursor.fetchall()
        columns = [row[1] for row in rows]
        
        for col, definition in [
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("excluded_keywords", "TEXT"),
            ("price_drop_threshold", "REAL DEFAULT 0"),
            ("only_photos", "BOOLEAN DEFAULT FALSE"),
            ("channel_id", "INTEGER"),
        ]:
            if col not in columns:
                await self.connection.execute(f"ALTER TABLE searches ADD COLUMN {col} {definition}")
        await self.connection.commit()

    async def close(self):
        if self.connection:
            await self.connection.close()

    # ── Users ──────────────────────────────────────

    async def get_or_create_user(self, user_id: int, username: Optional[str] = None, referrer_id: Optional[int] = None) -> Dict[str, Any]:
        cursor = await self.connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

        if not row:
            trial_until = datetime.now() + timedelta(days=config.TRIAL_DAYS)
            is_admin = 1 if user_id == config.ADMIN_ID else 0
            await self.connection.execute(
                "INSERT INTO users (user_id, username, subscription_until, tariff_plan, is_admin, is_active, is_banned, referrer_id) "
                "VALUES (?, ?, ?, 'basic', ?, TRUE, FALSE, ?)",
                (user_id, username, trial_until, is_admin, referrer_id)
            )
            cursor = await self.connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()

            if referrer_id and referrer_id != user_id:
                await self._reward_referrer(referrer_id)

        else:
            row_dict = dict(row)
            if username and row_dict["username"] != username:
                await self.connection.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
                cursor = await self.connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()

            if user_id == config.ADMIN_ID and not row_dict["is_admin"]:
                await self.connection.execute("UPDATE users SET is_admin = TRUE WHERE user_id = ?", (user_id,))
                cursor = await self.connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()

        return dict(row)

    async def _reward_referrer(self, referrer_id: int):
        await self.give_subscription_by_identifier(str(referrer_id), 1)

    async def check_subscription(self, user_id: int) -> bool:
        cursor = await self.connection.execute("SELECT subscription_until, is_banned FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return True
        if row["is_banned"]:
            return False
        sub_until = row["subscription_until"]
        if isinstance(sub_until, str):
            sub_until = datetime.fromisoformat(sub_until)
        return datetime.now() < sub_until

    async def deactivate_user(self, user_id: int):
        await self.connection.execute("UPDATE users SET is_active = FALSE WHERE user_id = ?", (user_id,))
        await self.connection.commit()

    async def is_banned(self, user_id: int) -> bool:
        cursor = await self.connection.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return bool(row and row["is_banned"])

    async def ban_user(self, user_id: int):
        await self.connection.execute("UPDATE users SET is_banned = TRUE WHERE user_id = ?", (user_id,))
        await self.connection.commit()

    async def unban_user(self, user_id: int):
        await self.connection.execute("UPDATE users SET is_banned = FALSE WHERE user_id = ?", (user_id,))
        await self.connection.commit()

    async def give_subscription_by_identifier(self, identifier: str, days: int) -> bool:
        return await self._give_subscription(identifier, days)

    async def _give_subscription(self, identifier: str, days: int) -> bool:
        if identifier.isdigit():
            cursor = await self.connection.execute("SELECT * FROM users WHERE user_id = ?", (int(identifier),))
        else:
            cursor = await self.connection.execute("SELECT * FROM users WHERE username = ?", (identifier.replace("@", ""),))
        
        row = await cursor.fetchone()
        if not row:
            return False

        current_sub = row["subscription_until"]
        if isinstance(current_sub, str):
            current_sub = datetime.fromisoformat(current_sub)
        base_time = max(datetime.now(), current_sub)
        new_sub = base_time + timedelta(days=days)

        await self.connection.execute(
            "UPDATE users SET subscription_until = ?, is_active = TRUE WHERE user_id = ?",
            (new_sub, row["user_id"])
        )
        await self.connection.commit()
        return True

    async def set_tariff_plan(self, user_id: int, plan_key: str):
        await self.connection.execute("UPDATE users SET tariff_plan = ? WHERE user_id = ?", (plan_key, user_id))
        await self.connection.commit()

    async def get_tariff_plan(self, user_id: int) -> str:
        cursor = await self.connection.execute("SELECT tariff_plan FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row["tariff_plan"] if row else "basic"

    async def count_user_searches(self, user_id: int) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM searches WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_all_users(self) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_active_users_count(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_paying_users_count(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users WHERE tariff_plan = 'pro'")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_total_users_count(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_referrals_count(self, user_id: int) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ── Searches ───────────────────────────────────

    async def get_user_searches(self, user_id: int, active_only: bool = False) -> List[Dict[str, Any]]:
        if active_only:
            cursor = await self.connection.execute("SELECT * FROM searches WHERE user_id = ? AND is_active = TRUE ORDER BY id", (user_id,))
        else:
            cursor = await self.connection.execute("SELECT * FROM searches WHERE user_id = ? ORDER BY id", (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_all_active_searches(self) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("""
            SELECT s.* FROM searches s
            JOIN users u ON s.user_id = u.user_id
            WHERE u.is_active = TRUE AND u.is_banned = FALSE AND s.is_active = TRUE
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def add_search(self, user_id: int, title: str, url: str, min_price: float = 0, max_price: float = 0,
                          excluded_keywords: str = None, price_drop_threshold: float = 0.0):
        await self.connection.execute(
            "INSERT INTO searches (user_id, title, url, min_price, max_price, is_active, excluded_keywords, price_drop_threshold) "
            "VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)",
            (user_id, title, url, min_price, max_price, excluded_keywords, price_drop_threshold)
        )
        await self.connection.commit()

    async def delete_search(self, search_id: int, user_id: int):
        await self.connection.execute("DELETE FROM searches WHERE id = ? AND user_id = ?", (search_id, user_id))
        await self.connection.commit()

    async def toggle_search_active(self, search_id: int, user_id: int) -> bool:
        cursor = await self.connection.execute("SELECT is_active FROM searches WHERE id = ? AND user_id = ?", (search_id, user_id))
        row = await cursor.fetchone()
        if not row:
            return False
        new_state = not row["is_active"]
        await self.connection.execute("UPDATE searches SET is_active = ? WHERE id = ? AND user_id = ?", (new_state, search_id, user_id))
        await self.connection.commit()
        return new_state

    async def update_search(self, search_id: int, user_id: int, **kwargs):
        allowed = {"title", "url", "min_price", "max_price", "excluded_keywords", "price_drop_threshold", "only_photos", "channel_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [search_id, user_id]
        await self.connection.execute(f"UPDATE searches SET {set_clause} WHERE id = ? AND user_id = ?", tuple(values))
        await self.connection.commit()

    async def get_search_by_id(self, search_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = await self.connection.execute("SELECT * FROM searches WHERE id = ? AND user_id = ?", (search_id, user_id))
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ── Sent Ads ───────────────────────────────────

    async def is_ad_sent(self, ad_id: str, search_id: int) -> tuple[bool, float]:
        cursor = await self.connection.execute(
            "SELECT price FROM sent_ads WHERE ad_id = ? AND search_id = ?",
            (ad_id, search_id)
        )
        row = await cursor.fetchone()
        if row:
            return True, row["price"]
        return False, 0.0

    async def save_sent_ad(self, user_id: int, ad_id: str, search_id: int, price: float):
        await self.connection.execute(
            """
            INSERT OR REPLACE INTO sent_ads (user_id, ad_id, search_id, price)
            VALUES (?, ?, ?, ?)
            """,
            user_id, ad_id, search_id, price
        )
        await self.connection.commit()

    async def cleanup_old_sent_ads(self, days: int = 30):
        await self.connection.execute(
            "DELETE FROM sent_ads WHERE ad_id NOT IN "
            "(SELECT ad_id FROM sent_ads GROUP BY ad_id HAVING MAX(id) > "
            f"(SELECT MAX(id) - 5000 FROM sent_ads))"
        )
        await self.connection.commit()

    async def get_user_stats(self, user_id: int) -> Dict[str, int]:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM sent_ads WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        total_ads = row[0] if row else 0
        cursor = await self.connection.execute("SELECT COUNT(*) FROM searches WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        total_searches = row[0] if row else 0
        return {"total_ads": total_ads, "total_searches": total_searches}

    # ── Promocodes ─────────────────────────────────

    async def create_promocode(self, code: str, days: int, max_uses: int = -1) -> bool:
        try:
            await self.connection.execute(
                "INSERT INTO promocodes (code, days, max_uses, used_count, is_active) VALUES (?, ?, ?, 0, TRUE)",
                (code.upper(), days, max_uses)
            )
            await self.connection.commit()
            return True
        except Exception:
            return False

    async def redeem_promocode(self, code: str, user_id: int) -> tuple[bool, str]:
        code = code.upper().strip()
        cursor = await self.connection.execute("SELECT * FROM promocodes WHERE code = ? AND is_active = TRUE", (code,))
        promo = await cursor.fetchone()
        if not promo:
            return False, "Промокод не найден или неактивен."

        if promo["max_uses"] >= 0 and promo["used_count"] >= promo["max_uses"]:
            return False, "Лимит использований промокода исчерпан."

        cursor = await self.connection.execute("SELECT 1 FROM promo_redemptions WHERE user_id = ? AND code = ?", (user_id, code))
        if await cursor.fetchone():
            return False, "Вы уже использовали этот промокод."

        success = await self._give_subscription(str(user_id), promo["days"])
        if not success:
            return False, "Ошибка применения промокода."

        await self.connection.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
        await self.connection.execute("INSERT INTO promo_redemptions (user_id, code) VALUES (?, ?)", (user_id, code))
        await self.connection.commit()
        return True, f"Промокод активирован! +{promo['days']} дней подписки."

    async def list_promocodes(self) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_promocode(self, code: str) -> bool:
        cursor = await self.connection.execute("DELETE FROM promocodes WHERE code = ?", (code.upper(),))
        await self.connection.commit()
        return cursor.rowcount > 0

    # ── Language & Preferences ─────────────────────

    async def get_user_language(self, user_id: int) -> str:
        cursor = await self.connection.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row["language"] if row else "ru"

    async def set_user_language(self, user_id: int, language: str):
        await self.connection.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
        await self.connection.commit()

    async def get_quiet_hours(self, user_id: int) -> tuple[str, str]:
        cursor = await self.connection.execute("SELECT quiet_start, quiet_end FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return (row["quiet_start"], row["quiet_end"]) if row else ("00", "08")

    async def set_quiet_hours(self, user_id: int, quiet_start: str, quiet_end: str):
        await self.connection.execute(
            "UPDATE users SET quiet_start = ?, quiet_end = ? WHERE user_id = ?",
            (quiet_start, quiet_end, user_id)
        )
        await self.connection.commit()

    async def update_last_active(self, user_id: int):
        await self.connection.execute("UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
        await self.connection.commit()

    # ── Weekly Stats (Pro Analytics) ───────────────

    async def save_weekly_stats(self, user_id: int, search_id: int, week_start: str,
                                total_ads: int, prices: list[float]):
        avg_price = sum(prices) / len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        await self.connection.execute(
            """
            INSERT OR REPLACE INTO weekly_stats (user_id, search_id, week_start, total_ads, avg_price, min_price, max_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, search_id, week_start, total_ads, avg_price, min_price, max_price)
        )
        await self.connection.commit()

    async def get_user_weekly_stats(self, user_id: int) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute(
            "SELECT * FROM weekly_stats WHERE user_id = ? ORDER BY week_start DESC LIMIT 8",
            user_id
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ── Badges (Gamification) ──────────────────────

    async def get_user_badges(self, user_id: int) -> List[Dict[str, Any]]:
        cursor = await self.connection.execute(
            """
            SELECT b.*, ub.earned_at FROM user_badges ub
            JOIN badges b ON ub.badge_key = b.key
            WHERE ub.user_id = ?
            ORDER BY ub.earned_at DESC
            """,
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def check_and_award_badges(self, user_id: int) -> List[str]:
        cursor = await self.connection.execute("SELECT * FROM badges")
        badges = await cursor.fetchall()
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM sent_ads WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        total_ads = row[0] if row else 0
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM searches WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        total_searches = row[0] if row else 0
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        row = await cursor.fetchone()
        referrals = row[0] if row else 0
        
        cursor = await self.connection.execute("SELECT tariff_plan FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        tariff = row["tariff_plan"] if row else "basic"

        cursor = await self.connection.execute("SELECT badge_key FROM user_badges WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        earned_keys = {r["badge_key"] for r in rows}

        earned = []
        for badge in badges:
            if badge["key"] in earned_keys:
                continue

            should_earn = False
            condition = badge["condition"]
            if condition == "first_search" and total_searches >= 1:
                should_earn = True
            elif condition == "searcher" and total_searches >= 10:
                should_earn = True
            elif condition == "pro_searcher" and total_searches >= 50:
                should_earn = True
            elif condition == "first_ad" and total_ads >= 1:
                should_earn = True
            elif condition == "collector" and total_ads >= 100:
                should_earn = True
            elif condition == "social" and referrals >= 1:
                should_earn = True
            elif condition == "influencer" and referrals >= 5:
                should_earn = True
            elif condition == "pro_member" and tariff == "pro":
                should_earn = True
            elif condition == "vip" and tariff == "pro" and total_ads >= 200:
                should_earn = True

            if should_earn:
                await self.connection.execute(
                    "INSERT INTO user_badges (user_id, badge_key) VALUES (?, ?)",
                    (user_id, badge["key"])
                )
                earned.append(badge["key"])

        if earned:
            await self.connection.commit()
        return earned

    # ── Channels (Group Mode) ──────────────────────

    async def add_channel_for_search(self, search_id: int, user_id: int, channel_id: int) -> bool:
        await self.connection.execute(
            "UPDATE searches SET channel_id = ? WHERE id = ? AND user_id = ?",
            (channel_id, search_id, user_id)
        )
        await self.connection.commit()
        return True

    async def get_search_channel(self, search_id: int, user_id: int) -> Optional[int]:
        cursor = await self.connection.execute(
            "SELECT channel_id FROM searches WHERE id = ? AND user_id = ?",
            search_id, user_id
        )
        row = await cursor.fetchone()
        return row["channel_id"] if row and row["channel_id"] else None

    # ── Inactivity Tracking ────────────────────────

    async def get_inactive_users(self, days: int = 7) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        cursor = await self.connection.execute(
            "SELECT user_id, username, last_active_at FROM users WHERE last_active_at < ? AND is_active = TRUE",
            cutoff.isoformat()
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
