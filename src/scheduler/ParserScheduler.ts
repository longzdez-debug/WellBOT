import { DatabaseService } from '../database/DatabaseService';
import { ParserFactory } from '../parsers/ParserFactory';
import { BotHandler } from '../bot/BotHandler';
import { logger } from '../utils/logger';

export class ParserScheduler {
  private db: DatabaseService;
  private bot: BotHandler;
  private intervalId: NodeJS.Timeout | null = null;
  private intervalMs: number;

  constructor(db: DatabaseService, bot: BotHandler) {
    this.db = db;
    this.bot = bot;
    
    const intervalSeconds = parseInt(process.env.PARSE_INTERVAL_SECONDS || '30', 10);
    this.intervalMs = intervalSeconds * 1000;
    
    logger.info('Parser scheduler configured', { 
      intervalSeconds, 
      intervalMinutes: (intervalSeconds / 60).toFixed(1) 
    });
  }

  start(): void {
    // Запускаем сразу при старте
    this.runParsing();
    
    // Затем запускаем по интервалу — без блокировки, каждый цикл работает независимо
    this.intervalId = setInterval(() => {
      this.runParsing();
    }, this.intervalMs);

    logger.info('Parser scheduler started', { 
      intervalMs: this.intervalMs,
      intervalMinutes: (this.intervalMs / 60000).toFixed(1)
    });
  }

  async runParsing(): Promise<void> {
    const startTime = Date.now();

    try {
      const links = await this.db.getActiveLinks();
      logger.info('🔄 Parsing cycle started', { linksCount: links.length, intervalMs: this.intervalMs });

      const processedPairs = new Set<string>();
      const uniqueLinks = links.filter(link => {
        const key = `${link.user_id}|${link.url}`;
        if (processedPairs.has(key)) {
          logger.warn('Skipping duplicate link in this cycle (same user + same URL)', {
            linkId: link.id,
            userId: link.user_id,
            url: link.url,
          });
          return false;
        }
        processedPairs.add(key);
        return true;
      });

      // Собираем ВСЕ новые объявления по всем ссылкам
      const allNewAds: Array<{ ad: any; telegramId: number }> = [];
      const allPriceDrops: Array<{ drop: any; telegramId: number; userId: number }> = [];
      const batchSize = 10;
      let totalNewAds = 0;

      for (let i = 0; i < uniqueLinks.length; i += batchSize) {
        const batch = uniqueLinks.slice(i, i + batchSize);
        const results = await Promise.allSettled(batch.map(link => this.parseLink(link)));
        
        for (let j = 0; j < results.length; j++) {
          const result = results[j];
          const link = batch[j];
          if (result.status === 'fulfilled' && result.value) {
            const { newAds, priceDrops } = result.value;
            totalNewAds += newAds.length;
            
            const user = await this.db.getUserById(link.user_id);
            if (user) {
              for (const ad of newAds) {
                allNewAds.push({ ad, telegramId: user.telegram_id });
              }
              for (const drop of priceDrops) {
                allPriceDrops.push({ drop, telegramId: user.telegram_id, userId: user.id });
              }
            }
          } else {
            logger.error('Batch parseLink error', { 
              linkId: link.id, 
              error: (result as PromiseRejectedResult).reason?.message 
            });
          }
        }
        
        if (i + batchSize < uniqueLinks.length) {
          await this.sleep(100);
        }
      }

      // Дедупликация на уровне пользователя: telegramId + external_id
      const notifiedDmByUser = new Set<string>();
      const notifiedChannelByUser = new Set<string>();

      // Отправляем новые объявления (без дублей)
      for (const { ad, telegramId } of allNewAds) {
        const dmKey = `${telegramId}|${ad.external_id}`;
        if (notifiedDmByUser.has(dmKey)) {
          logger.info('Skipping duplicate ad (already sent this cycle)', { telegramId, adId: ad.external_id });
          continue;
        }
        notifiedDmByUser.add(dmKey);
        
        logger.info('Sending notification for ad', { 
          adId: ad.id, 
          telegramId,
          imageUrl: ad.image_url || 'NO IMAGE'
        });
        await this.bot.sendNotification(telegramId, ad);
        await this.sleep(100);
      }

      // Отправляем уведомления о снижении цены (без дублей)
      for (const { drop, telegramId, userId } of allPriceDrops) {
        const dmKey = `${telegramId}|${drop.externalId}`;
        if (!notifiedDmByUser.has(dmKey)) {
          notifiedDmByUser.add(dmKey);
          logger.info('Sending price drop notification', { telegramId });
          await this.bot.sendPriceDropNotification(telegramId, drop);
        }
        
        const channelSub = await this.db.getActiveChannelSubscription(userId);
        if (channelSub) {
          const chKey = `${channelSub.channel_id}|${drop.externalId}`;
          if (!notifiedChannelByUser.has(chKey)) {
            notifiedChannelByUser.add(chKey);
            try {
              await this.bot.sendPriceDropNotification(channelSub.channel_id, drop);
              logger.info('Sent price drop to channel', { channelId: channelSub.channel_id });
            } catch (error: any) {
              logger.error('Failed to send price drop to channel', { 
                adId: drop.adId, 
                channelId: channelSub.channel_id,
                error: error.message
              });
            }
          }
        }
        await this.sleep(100);
      }

      const duration = Date.now() - startTime;
      logger.info('Parsing cycle completed', { 
        duration: `${duration}ms`, 
        linksCount: uniqueLinks.length,
        totalNewAds,
        uniqueAdsSent: notifiedDmByUser.size,
        newAdsDetected: totalNewAds,
        cycleTime: `${(duration/1000).toFixed(1)}s`
      });
    } catch (error: any) {
      logger.error('Parsing cycle failed', { error: error.message });
    }
  }

  private async parseLink(link: any): Promise<{ newAds: any[]; priceDrops: any[] } | null> {
    const newAds: any[] = [];
    const priceDrops: any[] = [];
    
    try {
      const parser = ParserFactory.getParser(link.platform);
      if (!parser) {
        logger.error('No parser found for platform', { platform: link.platform, linkId: link.id });
        return { newAds, priceDrops };
      }

      const parsePromise = parser.parseUrl(link.url);
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('Parse timeout after 5 minutes')), 300000);
      });
      let ads: any[];
      try {
        ads = await Promise.race([parsePromise, timeoutPromise]);
      } catch {
        return { newAds, priceDrops };
      }
      
      if (!Array.isArray(ads)) {
        logger.error('Parser returned non-array', { linkId: link.id, platform: link.platform, result: ads });
        return { newAds, priceDrops };
      }
      
      await this.db.updateLastParsed(link.id);

      if (link.error_count > 0) {
        await this.db.resetErrorCount(link.id);
      }

      const skippedCount = { alreadyExists: 0, filtered: 0 };
      const processedExternalIds = new Set<string>();

      logger.info('Starting to process ads', { 
        linkId: link.id, 
        totalAdsInResult: ads.length,
        externalIds: ads.map(a => `${a.external_id}: ${a.title}`)
      });

      for (let i = 0; i < ads.length; i++) {
        const adData = ads[i];
        
        if (processedExternalIds.has(adData.external_id)) {
          skippedCount.filtered++;
          continue;
        }
        processedExternalIds.add(adData.external_id);
        
        const isNew = await this.db.isNewAdForUser(link.user_id, adData.external_id);
        if (!isNew) {
          skippedCount.alreadyExists++;
          logger.info('Skipping existing ad (user-level dedup)', { 
            linkId: link.id, 
            external_id: adData.external_id,
            title: adData.title,
            location: adData.location || adData.address || 'unknown'
          });
          await this.checkPriceDrop(link.id, adData.external_id, adData.price, priceDrops);
          continue;
        }
        
        const ad = await this.db.createAd(link.id, adData);
        if (ad) {
          newAds.push(ad);
          logger.info('📢 NEW AD DETECTED!', { 
            linkId: link.id, 
            external_id: adData.external_id, 
            title: adData.title,
            price: adData.price,
            location: adData.location || adData.address || 'unknown',
            ad_url: adData.ad_url,
            timestamp: new Date().toISOString()
          });
        } else {
          logger.error('Failed to save ad (returned null)', { 
            linkId: link.id, 
            external_id: adData.external_id, 
            title: adData.title
          });
        }
      }

      logger.info('Processed ads for link', { 
        linkId: link.id, 
        totalAds: ads.length, 
        newAds: newAds.length,
        skipped: skippedCount
      });

      return { newAds, priceDrops };
    } catch (error: any) {
      logger.error('Failed to parse link', { linkId: link.id, url: link.url, error: error.message });
      
      await this.db.incrementErrorCount(link.id);
      const currentLink = await this.db.getLink(link.id);
      
      if (currentLink && currentLink.error_count >= 5) {
        await this.db.markLinkInactive(link.id);
        logger.warn('Link marked as inactive due to errors', { linkId: link.id, errorCount: currentLink.error_count });
      }
      
      return { newAds, priceDrops };
    }
  }

  private async checkPriceDrop(linkId: number, externalId: string, newPrice: string, priceDrops: any[]): Promise<void> {
    try {
      const lastPrice = await this.db.getLastPriceForAd(linkId, externalId);
      if (!lastPrice) return;
      
      const oldPriceNum = this.db.parsePriceToNumber(lastPrice.price);
      const newPriceNum = this.db.parsePriceToNumber(newPrice);
      
      if (oldPriceNum === null || newPriceNum === null) return;

      // Цена упала
      if (newPriceNum < oldPriceNum) {
        const changePercent = ((oldPriceNum - newPriceNum) / oldPriceNum * 100).toFixed(1);
        
        // Атомарно фиксируем снижение. Уникальный индекс (ad_id, old_price, new_price)
        // не даёт создать дубликат, даже если две ссылки обрабатываются параллельно.
        // Запись уже была — значит такое снижение уже уведомили, пропускаем.
        const recorded = await this.db.createPriceDropRecord(lastPrice.adId, externalId, lastPrice.price, newPrice, parseFloat(changePercent));
        if (!recorded) {
          logger.info('Price drop already notified, skipping', { 
            linkId, 
            externalId, 
            oldPrice: lastPrice.price, 
            newPrice 
          });
        } else {
          priceDrops.push({
            adId: lastPrice.adId,
            oldPrice: lastPrice.price,
            newPrice: newPrice,
            changePercent: changePercent,
            externalId: externalId,
            linkId: linkId
          });
          
          logger.info('Price drop detected', { 
            linkId, 
            externalId, 
            oldPrice: lastPrice.price, 
            newPrice, 
            changePercent 
          });
        }
      }
      
      // Синхронизируем сохранённую цену с актуальной.
      // Без этого одно и то же снижение будет детектиться на каждом цикле парсинга.
      if (oldPriceNum !== newPriceNum) {
        await this.db.updateAdPrice(lastPrice.adId, newPrice);
      }
    } catch (error: any) {
      logger.error('Failed to check price drop', { 
        linkId, 
        externalId, 
        error: error.message 
      });
    }
  }

  private async sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
    logger.info('Parser scheduler stopped');
  }

  /** Запуск парсинга вручную (например, после добавления новой ссылки) */
  triggerParse(): void {
    // Запускаем сразу, не дожидаясь следующего цикла
    this.runParsing().catch(err => {
      logger.error('Triggered parse failed', { error: err.message });
    });
  }
}
