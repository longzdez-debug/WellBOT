import { DatabaseService } from '../database/DatabaseService';
import { ParserFactory } from '../parsers/ParserFactory';
import { BotHandler } from '../bot/BotHandler';
import { logger } from '../utils/logger';

export class ParserScheduler {
  private db: DatabaseService;
  private bot: BotHandler;
  private intervalId: NodeJS.Timeout | null = null;
  private isRunning: boolean = false;
  private intervalMs: number;

  constructor(db: DatabaseService, bot: BotHandler) {
    this.db = db;
    this.bot = bot;
    
    // Читаем интервал из переменной окружения (в секундах)
    // По умолчанию 60 секунд (1 минута) — уведомления приходят быстро
    const intervalSeconds = parseInt(process.env.PARSE_INTERVAL_SECONDS || '60', 10);
    this.intervalMs = intervalSeconds * 1000;
    
    logger.info('Parser scheduler configured', { 
      intervalSeconds, 
      intervalMinutes: (intervalSeconds / 60).toFixed(1) 
    });
  }

  start(): void {
    // Запускаем сразу при старте
    this.runParsing();
    
    // Затем запускаем по интервалу
    this.intervalId = setInterval(async () => {
      if (this.isRunning) {
        logger.warn('Previous parsing still running, skipping this cycle');
        return;
      }
      await this.runParsing();
    }, this.intervalMs);

    logger.info('Parser scheduler started', { 
      intervalMs: this.intervalMs,
      intervalMinutes: (this.intervalMs / 60000).toFixed(1)
    });
  }

  async runParsing(): Promise<void> {
    this.isRunning = true;
    const startTime = Date.now();

    try {
      const links = await this.db.getActiveLinks();
      logger.info('Starting parsing cycle', { linksCount: links.length });

      // Защита от дубликатов ссылок: если у пользователя добавлена одна и та же
      // страница дважды, обрабатываем её один раз за цикл. Иначе каждое событие
      // (новое объявление / снижение цены) дублируется в ЛС и в канале.
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

      // Process links in parallel with limit.
      // Общие Set'ы для дедупа отправок в рамках ОДНОГО цикла парсинга:
      // даже если несколько ссылок (в т.ч. у разных пользователей) дают одно
      // и то же объявление, в ЛС и в канал оно уйдёт ровно один раз за цикл.
      const notifiedDm = new Set<string>();
      const notifiedChannel = new Set<string>();
      const batchSize = 10;
      let totalNewAds = 0;
      for (let i = 0; i < uniqueLinks.length; i += batchSize) {
        const batch = uniqueLinks.slice(i, i + batchSize);
        const results = await Promise.allSettled(batch.map(link => this.parseLink(link, notifiedDm, notifiedChannel)));
        
        // Track results for logging
        for (let j = 0; j < results.length; j++) {
          const result = results[j];
          const link = batch[j];
          if (result.status === 'fulfilled') {
            totalNewAds += result.value || 0;
          } else {
            logger.error('Batch parseLink error', { 
              linkId: link.id, 
              error: (result as PromiseRejectedResult).reason?.message 
            });
          }
        }
        
        // Small delay between batches
        if (i + batchSize < uniqueLinks.length) {
          await this.sleep(1000);
        }
      }

      const duration = Date.now() - startTime;
      logger.info('Parsing cycle completed', { 
        duration: `${duration}ms`, 
        linksCount: uniqueLinks.length,
        totalNewAds
      });
    } catch (error: any) {
      logger.error('Parsing cycle failed', { error: error.message });
    } finally {
      this.isRunning = false;
    }
  }

  private async parseLink(link: any, notifiedDm: Set<string>, notifiedChannel: Set<string>): Promise<number> {
    const newAds: any[] = [];
    const priceDrops: any[] = [];
    
    try {
      const parser = ParserFactory.getParser(link.platform);
      if (!parser) {
        logger.error('No parser found for platform', { platform: link.platform, linkId: link.id });
        return 0;
      }

      // Таймаут на парсинг — 5 минут максимум
      const parsePromise = parser.parseUrl(link.url);
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('Parse timeout after 5 minutes')), 300000);
      });
      let ads: any[];
      try {
        ads = await Promise.race([parsePromise, timeoutPromise]);
      } catch {
        return 0;
      }
      
      // Защита: парсер обязан вернуть массив
      if (!Array.isArray(ads)) {
        logger.error('Parser returned non-array', { linkId: link.id, platform: link.platform, result: ads });
        return 0;
      }
      
      await this.db.updateLastParsed(link.id);

      // Reset error count on successful parse
      if (link.error_count > 0) {
        await this.db.resetErrorCount(link.id);
      }

      // Process new ads
      const skippedCount = { alreadyExists: 0, filtered: 0 };
      const processedExternalIds = new Set<string>(); // Защита от дубликатов

      logger.info('Starting to process ads', { 
        linkId: link.id, 
        totalAdsInResult: ads.length,
        externalIds: ads.map(a => `${a.external_id}: ${a.title}`)
      });

      for (let i = 0; i < ads.length; i++) {
        const adData = ads[i];
        
        // Защита от дубликатов в результате парсинга
        if (processedExternalIds.has(adData.external_id)) {
          logger.info('Skipping duplicate external_id', { 
            linkId: link.id, 
            external_id: adData.external_id,
            title: adData.title
          });
          skippedCount.filtered++;
          continue;
        }
        processedExternalIds.add(adData.external_id);
        
        logger.info('Processing ad', { 
          linkId: link.id, 
          index: i,
          external_id: adData.external_id, 
          title: adData.title,
          price: adData.price,
          location: adData.location || adData.address || 'unknown'
        });
        
        const isNew = await this.db.isNewAdForLink(link.id, adData.external_id);
        if (!isNew) {
          skippedCount.alreadyExists++;
          logger.info('Skipping existing ad', { 
            linkId: link.id, 
            external_id: adData.external_id, 
            title: adData.title,
            location: adData.location || adData.address || 'unknown'
          });
          
          // Проверяем снижение цены
          await this.checkPriceDrop(link.id, adData.external_id, adData.price, priceDrops);
          continue;
        }
        
        logger.info('Creating ad in database', { 
          linkId: link.id, 
          external_id: adData.external_id 
        });
        
        const ad = await this.db.createAd(link.id, adData);
        if (ad) {
          newAds.push(ad);
          logger.info('New ad saved', { 
            linkId: link.id, 
            external_id: adData.external_id, 
            title: adData.title,
            price: adData.price,
            location: adData.location || adData.address || 'unknown'
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
        skipped: skippedCount,
        newAdsTitles: newAds.map(a => `${a.title} (${a.location || a.address || 'N/A'})`)
      });

      // Send notifications for new ads (только в личку, не в канал!)
      if (newAds.length > 0) {
        logger.info('Attempting to send notifications', { 
          linkId: link.id, 
          userId: link.user_id,
          newAdsCount: newAds.length 
        });
        
        const user = await this.db.getUserById(link.user_id);
        if (!user) {
          logger.error('User not found for link', { linkId: link.id, userId: link.user_id });
          return newAds.length;
        }
        
        logger.info('User found, sending notifications', { 
          userId: user.id, 
          telegramId: user.telegram_id 
        });
        
        // Уведомляем обо всех новых объявлениях ТОЛЬКО в личку.
        // Общий для цикла Set не даёт отправить одно объявление дважды,
        // если на него подписаны несколько ссылок одного пользователя.
        for (const ad of newAds) {
          try {
            const dmKey = `${user.telegram_id}|${ad.external_id}`;
            if (notifiedDm.has(dmKey)) {
              logger.info('Skipping duplicate notification (already sent this cycle)', {
                telegramId: user.telegram_id,
                adId: ad.external_id,
              });
              continue;
            }
            notifiedDm.add(dmKey);

            logger.info('Sending notification for ad', { 
              adId: ad.id, 
              telegramId: user.telegram_id,
              imageUrl: ad.image_url || 'NO IMAGE'
            });
            await this.bot.sendNotification(user.telegram_id, ad);
            
            // Delay between notifications to prevent message merging
            await this.sleep(3000);
          } catch (error: any) {
            logger.error('Failed to send notification', { 
              linkId: link.id, 
              adId: ad.id, 
              error: error.message,
              stack: error.stack
            });
          }
        }
        
        logger.info('New ads found and notified', { 
          linkId: link.id, 
          totalNew: newAds.length,
          notified: newAds.length
        });
      }
      
      // Send price drop notifications (в канал И в личку)
      if (priceDrops.length > 0) {
        logger.info('Price drops detected', { 
          linkId: link.id, 
          priceDropsCount: priceDrops.length 
        });
        
        const user = await this.db.getUserById(link.user_id);
        if (user) {
          // Получаем привязанный канал
          const channelSub = await this.db.getActiveChannelSubscription(user.id);
          
          for (const priceDrop of priceDrops) {
            try {
              // В ЛС — один раз за цикл (общий Set)
              const dmKey = `${user.telegram_id}|${priceDrop.externalId}`;
              if (!notifiedDm.has(dmKey)) {
                notifiedDm.add(dmKey);
                logger.info('Sending price drop notification', { 
                  adId: priceDrop.adId, 
                  telegramId: user.telegram_id 
                });
                await this.bot.sendPriceDropNotification(user.telegram_id, priceDrop);
              }
              
              // Если есть канал — отправляем туда тоже (один раз за цикл)
              if (channelSub) {
                const chKey = `${channelSub.channel_id}|${priceDrop.externalId}`;
                if (!notifiedChannel.has(chKey)) {
                  notifiedChannel.add(chKey);
                  try {
                    await this.bot.sendPriceDropNotification(channelSub.channel_id, priceDrop);
                    logger.info('Sent price drop to channel', { 
                      adId: priceDrop.adId, 
                      channelId: channelSub.channel_id 
                    });
                  } catch (error: any) {
                    logger.error('Failed to send price drop to channel', { 
                      linkId: link.id, 
                      adId: priceDrop.adId, 
                      channelId: channelSub.channel_id,
                      error: error.message
                    });
                  }
                }
              }
              
              await this.sleep(3000);
            } catch (error: any) {
              logger.error('Failed to send price drop notification', { 
                linkId: link.id, 
                adId: priceDrop.adId, 
                error: error.message,
                stack: error.stack
              });
            }
          }
        }
      }
    } catch (error: any) {
      logger.error('Failed to parse link', { linkId: link.id, url: link.url, error: error.message });
      
      await this.db.incrementErrorCount(link.id);
      const currentLink = await this.db.getLink(link.id);
      
      if (currentLink && currentLink.error_count >= 5) {
        await this.db.markLinkInactive(link.id);
        logger.warn('Link marked as inactive due to errors', { linkId: link.id, errorCount: currentLink.error_count });
      }
      
      return 0;
    }
    
    return newAds.length;
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
    if (this.isRunning) {
      logger.info('Parse already running, skipping trigger');
      return;
    }
    // Запускаем сразу, не дожидаясь следующего цикла
    this.runParsing().catch(err => {
      logger.error('Triggered parse failed', { error: err.message });
    });
  }
}
