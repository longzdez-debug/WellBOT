import TelegramBot from 'node-telegram-bot-api';
import { FormattedAd } from './AdPresenter';
import { logger } from '../utils/logger';

export class TelegramSender {
  private bot: TelegramBot;
  // Telegram API лимит: ~30 сообщений/сек, но безопасно — 1 сообщение/сек
  private lastSendTime: number = 0;
  private readonly MIN_SEND_INTERVAL_MS = 1000; // Минимум 1 секунда между сообщениями
  private readonly MAX_MEDIA_PER_GROUP = 10; // Telegram лимит для media group
  private retryAfterTimer: number = 0; // Таймер для обработки 429

  constructor(bot: TelegramBot) {
    this.bot = bot;
  }

  private async waitForRateLimit(): Promise<void> {
    // Обработка 429 (Too Many Requests) от Telegram
    if (this.retryAfterTimer > Date.now()) {
      const waitMs = this.retryAfterTimer - Date.now();
      logger.warn('Telegram rate limited (429), waiting', { waitMs });
      await new Promise(resolve => setTimeout(resolve, waitMs));
    }

    const now = Date.now();
    const timeSinceLastSend = now - this.lastSendTime;
    
    if (timeSinceLastSend < this.MIN_SEND_INTERVAL_MS) {
      const waitTime = this.MIN_SEND_INTERVAL_MS - timeSinceLastSend;
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
    
    this.lastSendTime = Date.now();
  }

  private handleTelegramError(error: any): void {
    // Обработка 429 Too Many Requests
    if (error.response?.statusCode === 429) {
      const retryAfter = error.response?.body?.retry_after || 5;
      this.retryAfterTimer = Date.now() + retryAfter * 1000;
      logger.error('Telegram rate limited (429)', { retryAfter });
    }
    
    // Если пользователь заблокировал бота — ничего не делаем
    if (error.response?.statusCode === 403) {
      logger.warn('User blocked the bot', { chatId: 0 });
    }
  }

  async send(chatId: number, formatted: FormattedAd): Promise<void> {
    try {
      await this.waitForRateLimit();

      // Media group (до 10 фото — лимит Telegram)
      // В media: [фото_товара, карта] — всё в одной группе
      // Текст прикреплён к первому фото
      if (formatted.media && formatted.media.length >= 1) {
        // Отрезаем лишние фото (Telegram лимит — 10)
        const mediaToSend = formatted.media.slice(0, this.MAX_MEDIA_PER_GROUP);
        
        // Формируем массив для sendMediaGroup: первое фото с caption
        const inputMedia: TelegramBot.InputMediaPhoto[] = mediaToSend.map((url, index) => ({
          type: 'photo',
          media: url,
          caption: index === 0 ? formatted.text : undefined,
        }));
        
        try {
          await this.bot.sendMediaGroup(chatId, inputMedia);
          logger.info('Media group sent', { chatId, count: mediaToSend.length });
        } catch (error: any) {
          this.handleTelegramError(error);
          logger.warn('Failed to send media group, falling back to single photo', {
            error: error.response?.body?.description || error.message,
            count: mediaToSend.length,
          });
          // Fallback: отправляем первое фото с подписью
          await this.bot.sendPhoto(chatId, mediaToSend[0], {
            caption: formatted.text,
            parse_mode: 'HTML',
          });
        }
      } else {
        // Только текст (без фото и карты)
        await this.bot.sendMessage(chatId, formatted.text, {
          parse_mode: 'HTML',
        });
      }

      // location больше не используется — карта уже в media
    } catch (error: any) {
      this.handleTelegramError(error);
      logger.error('Failed to send Telegram message', {
        chatId,
        error: error.message,
        statusCode: error.response?.statusCode,
      });
    }
  }

  async sendBatch(chatId: number, ads: FormattedAd[]): Promise<void> {
    for (const ad of ads) {
      await this.send(chatId, ad);
    }
  }
}

