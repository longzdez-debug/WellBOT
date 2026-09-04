import { Pool } from 'pg';
import { readFileSync } from 'fs';
import { join } from 'path';
import { User, Link, Ad, Platform } from '../types';
import { logger } from '../utils/logger';

export class DatabaseService {
  private pool: Pool;

  constructor(connectionString: string) {
    this.pool = new Pool({
      connectionString,
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 10000,
    });

    this.pool.on('error', (err: Error) => {
      logger.error('Unexpected database error', { error: err.message });
    });
  }

  async initialize(): Promise<void> {
    try {
      const schemaPath = join(__dirname, 'schema.sql');
      const schema = readFileSync(schemaPath, 'utf-8');
      await this.pool.query(schema);
      logger.info('Database schema initialized');
    } catch (error) {
      logger.error('Failed to initialize database', { error });
      throw error;
    }
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  // User operations
  async createUser(telegramId: number, username: string | null): Promise<User> {
    const result = await this.pool.query<User>(
      'INSERT INTO users (telegram_id, username) VALUES ($1, $2) ON CONFLICT (telegram_id) DO UPDATE SET username = $2 RETURNING *',
      [telegramId, username]
    );
    return result.rows[0];
  }

  async getUser(telegramId: number): Promise<User | null> {
    const result = await this.pool.query<User>(
      'SELECT * FROM users WHERE telegram_id = $1',
      [telegramId]
    );
    return result.rows[0] || null;
  }

  async getUserById(userId: number): Promise<User | null> {
    const result = await this.pool.query<User>(
      'SELECT * FROM users WHERE id = $1',
      [userId]
    );
    return result.rows[0] || null;
  }

  // Link operations
  async createLink(userId: number, url: string, platform: Platform): Promise<Link> {
    const result = await this.pool.query<Link>(
      'INSERT INTO links (user_id, url, platform) VALUES ($1, $2, $3) RETURNING *',
      [userId, url, platform]
    );
    return result.rows[0];
  }

  async getUserLinks(userId: number): Promise<Link[]> {
    const result = await this.pool.query<Link>(
      'SELECT * FROM links WHERE user_id = $1 ORDER BY created_at DESC',
      [userId]
    );
    return result.rows;
  }

  async getUserLinksCount(userId: number): Promise<number> {
    const result = await this.pool.query<{ count: string }>(
      'SELECT COUNT(*) as count FROM links WHERE user_id = $1',
      [userId]
    );
    return parseInt(result.rows[0].count, 10);
  }

  async getLink(linkId: number): Promise<Link | null> {
    const result = await this.pool.query<Link>(
      'SELECT * FROM links WHERE id = $1',
      [linkId]
    );
    return result.rows[0] || null;
  }

  async deleteLink(linkId: number): Promise<void> {
    await this.pool.query('DELETE FROM links WHERE id = $1', [linkId]);
  }

  async getActiveLinks(): Promise<Link[]> {
    const result = await this.pool.query<Link>(
      'SELECT * FROM links WHERE is_active = true'
    );
    return result.rows;
  }

  async incrementErrorCount(linkId: number): Promise<void> {
    await this.pool.query(
      'UPDATE links SET error_count = error_count + 1 WHERE id = $1',
      [linkId]
    );
  }

  async markLinkInactive(linkId: number): Promise<void> {
    await this.pool.query(
      'UPDATE links SET is_active = false WHERE id = $1',
      [linkId]
    );
  }

  async updateLastParsed(linkId: number): Promise<void> {
    await this.pool.query(
      'UPDATE links SET last_parsed_at = CURRENT_TIMESTAMP WHERE id = $1',
      [linkId]
    );
  }

  async resetErrorCount(linkId: number): Promise<void> {
    await this.pool.query(
      'UPDATE links SET error_count = 0 WHERE id = $1',
      [linkId]
    );
  }

  // Ad operations
  async createAd(linkId: number, adData: Ad): Promise<Ad | null> {
    const result = await this.pool.query<Ad>(
      `INSERT INTO ads (link_id, external_id, title, description, price, image_url, ad_url, location, address, published_at, updated_at) 
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) 
       ON CONFLICT (external_id, link_id) DO NOTHING 
       RETURNING *`,
      [
        linkId, 
        adData.external_id, 
        adData.title, 
        adData.description || null, 
        adData.price || null, 
        adData.image_url || null, 
        adData.ad_url,
        adData.location || null,
        adData.address || null,
        adData.published_at || null,
        adData.updated_at || null
      ]
    );
    // При ON CONFLICT DO NOTHING rows может быть пустым, если ад уже существует
    return result.rows[0] || null;
  }

  async getAdByExternalId(externalId: string): Promise<Ad | null> {
    const result = await this.pool.query<Ad>(
      'SELECT * FROM ads WHERE external_id = $1',
      [externalId]
    );
    return result.rows[0] || null;
  }

  async isNewAd(externalId: string): Promise<boolean> {
    const ad = await this.getAdByExternalId(externalId);
    return ad === null;
  }

  async isNewAdForLink(linkId: number, externalId: string): Promise<boolean> {
    const result = await this.pool.query(
      'SELECT id FROM ads WHERE link_id = $1 AND external_id = $2',
      [linkId, externalId]
    );
    return result.rows.length === 0;
  }

  async isNewAdForUser(userId: number, externalId: string): Promise<boolean> {
    const result = await this.pool.query(
      `SELECT a.id FROM ads a 
       JOIN links l ON a.link_id = l.id 
       WHERE l.user_id = $1 AND a.external_id = $2`,
      [userId, externalId]
    );
    return result.rows.length === 0;
  }

  async getUserAdsCount(userId: number): Promise<{ linkId: number; linkPlatform: string; count: number }[]> {
    const result = await this.pool.query(
      `SELECT l.id as "linkId", l.platform as "linkPlatform", COUNT(a.id) as "count" 
       FROM links l 
       LEFT JOIN ads a ON a.link_id = l.id 
       WHERE l.user_id = $1 
       GROUP BY l.id`,
      [userId]
    );
    return result.rows;
  }

  async clearAdsByUserId(userId: number): Promise<number> {
    const userResult = await this.pool.query('SELECT id FROM links WHERE user_id = $1', [userId]);
    const linkIds = userResult.rows.map(r => r.id);
    
    if (linkIds.length === 0) return 0;
    
    const placeholders = linkIds.map((_, i) => `$${i + 2}`).join(', ');
    const result = await this.pool.query(
      `DELETE FROM ads WHERE link_id IN (${placeholders})`,
      [userId, ...linkIds]
    );
    return result.rowCount || 0;
  }

  // ============================================
  // Price history operations
  // ============================================
  
  // Извлекаем число из строки цены (например "1700.00 BYN" -> 1700)
  parsePriceToNumber(priceStr: string | null | undefined): number | null {
    if (!priceStr) return null;
    const match = priceStr.match(/([\d.]+)/);
    if (!match) return null;
    const num = parseFloat(match[1]);
    return isNaN(num) ? null : num;
  }

  // Получаем последнюю цену объявления
  async getLastPriceForAd(linkId: number, externalId: string): Promise<{ price: string; adId: number } | null> {
    const result = await this.pool.query(
      `SELECT a.price, a.id as ad_id 
       FROM ads a 
       WHERE a.link_id = $1 AND a.external_id = $2 
       ORDER BY a.updated_at DESC 
       LIMIT 1`,
      [linkId, externalId]
    );
    return result.rows[0] || null;
  }

  // Создаём запись о снижении цены.
  // INSERT ... ON CONFLICT DO NOTHING + уникальный индекс (external_id, old_price, new_price)
  // гарантируют, что одно и то же снижение будет зафиксировано ровно один раз.
  // Дедуп идёт по external_id объявления, а не по ad_id: одна и та же страница поиска
  // может быть добавлена несколько раз (и даже разными пользователями) — у каждой ссылки
  // будет своя запись ads со своим id, но с одинаковым external_id.
  async createPriceDropRecord(adId: number, externalId: string, oldPrice: string, newPrice: string, changePercent: number): Promise<boolean> {
    try {
      const result = await this.pool.query(
        `INSERT INTO price_history (ad_id, external_id, old_price, new_price, price_change_percent, notified_at) 
         VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
         ON CONFLICT (ad_id, old_price, new_price) DO NOTHING`,
        [adId, externalId, oldPrice, newPrice, changePercent]
      );
      return (result.rowCount || 0) > 0;
    } catch (error: any) {
      // Если нет уникального индекса — просто логируем и пропускаем
      logger.warn('Price drop record insert failed (no unique constraint)', { error: error.message });
      return false;
    }
  }

  // Обновляем сохранённую цену объявления.
  // Без этого одно и то же снижение будет детектиться на каждом цикле парсинга.
  async updateAdPrice(adId: number, newPrice: string): Promise<void> {
    await this.pool.query(
      'UPDATE ads SET price = $1 WHERE id = $2',
      [newPrice, adId]
    );
  }

  // ============================================
  // Channel subscription operations
  // ============================================
  
  async createChannelSubscription(userId: number, channelId: number, channelUsername: string | null, channelTitle: string | null): Promise<void> {
    await this.pool.query(
      `INSERT INTO channel_subscriptions (user_id, channel_id, channel_username, channel_title) 
       VALUES ($1, $2, $3, $4) 
       ON CONFLICT (user_id, channel_id) DO UPDATE SET 
         channel_username = EXCLUDED.channel_username,
         channel_title = EXCLUDED.channel_title,
         is_active = true`,
      [userId, channelId, channelUsername, channelTitle]
    );
  }

  async deleteChannelSubscription(userId: number, channelId: number): Promise<void> {
    await this.pool.query(
      `UPDATE channel_subscriptions SET is_active = false WHERE user_id = $1 AND channel_id = $2`,
      [userId, channelId]
    );
  }

  // Полностью отключает ВСЕ каналы пользователя.
  // Используется командой «Отключить канал», когда конкретный channel_id неизвестен.
  async deactivateAllChannelSubscriptions(userId: number): Promise<void> {
    await this.pool.query(
      `UPDATE channel_subscriptions SET is_active = false WHERE user_id = $1`,
      [userId]
    );
  }

  async getActiveChannelSubscription(userId: number): Promise<{ channel_id: number; channel_username: string | null; channel_title: string | null } | null> {
    const result = await this.pool.query(
      `SELECT channel_id, channel_username, channel_title 
       FROM channel_subscriptions 
       WHERE user_id = $1 AND is_active = true 
       ORDER BY created_at DESC 
       LIMIT 1`,
      [userId]
    );
    return result.rows[0] || null;
  }
}
