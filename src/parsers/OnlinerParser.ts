import * as cheerio from 'cheerio';
import { BaseParser } from './BaseParser';
import { Ad } from '../types';
import { logger } from '../utils/logger';

export class OnlinerParser extends BaseParser {
  platform = 'onliner' as const;

  async parseUrl(url: string): Promise<Ad[]> {
    try {
      const urlObj = new URL(url);
      
      // Check if it's r.onliner.by (real estate map)
      if (urlObj.hostname.includes('r.onliner')) {
        return await this.parseRealEstateMap(url);
      }
      
      // Regular baraholka/ab parsing
      const html = await this.fetchWithRetry(url);
      const $ = cheerio.load(html);
      const ads: Ad[] = [];

      // Baraholka parsing
      $('.classified__item, .vehicle-item').each((_: number, element: any) => {
        const $el = $(element);
        const link = $el.find('a.classified__link, a.vehicle-item__link').first();
        const title = link.find('.classified__title, .vehicle-item__title').text().trim();
        const priceEl = $el.find('.classified__price, .vehicle-item__price');
        const price = priceEl.text().trim();
        const imgEl = $el.find('img.classified__image, img.vehicle-item__image').first();
        const imageUrl = imgEl.attr('src') || imgEl.attr('data-src') || null;
        const adUrl = link.attr('href');

        if (title && adUrl) {
          const fullUrl = adUrl.startsWith('http') ? adUrl : `https://baraholka.onliner.by${adUrl}`;
          const externalId = adUrl.match(/\/(\d+)$/)?.[1] || adUrl;

          ads.push({
            external_id: `onliner_${externalId}`,
            title,
            price: price || '',
            image_url: imageUrl || undefined,
            ad_url: fullUrl,
          });
        }
      });

      logger.info('Onliner parsing successful', { url, adsCount: ads.length });
      return ads;
    } catch (error: any) {
      logger.error('Onliner parsing failed', { url, error: error.message });
      throw error;
    }
  }

  private async parseRealEstateMap(url: string): Promise<Ad[]> {
    try {
      // Parse URL to extract search parameters
      const urlObj = new URL(url);
      
      // Build API request
      const apiUrl = 'https://ak.api.onliner.by/search/apartments';
      const params: any = {
        page: 1,
        limit: 50
      };
      
      // Extract parameters from URL
      urlObj.searchParams.forEach((value, key) => {
        if (key.includes('rent_type')) {
          if (!params['rent_type[]']) params['rent_type[]'] = [];
          if (value.includes('1_room')) params['rent_type[]'].push('1_room');
          if (value.includes('2_rooms')) params['rent_type[]'].push('2_rooms');
          if (value.includes('3_rooms')) params['rent_type[]'].push('3_rooms');
        } else if (key.includes('price')) {
          if (key.includes('min')) params['price[min]'] = value;
          if (key.includes('max')) params['price[max]'] = value;
        } else if (key === 'currency') {
          params.currency = value;
        } else if (key === 'only_owner') {
          params.only_owner = value === 'true';
        }
      });

      logger.info('Making Onliner API request', { apiUrl, params });
      
      const response = await this.axiosInstance.get(apiUrl, {
        params,
        headers: {
          'User-Agent': this.getRandomUserAgent(),
          'Host': 'ak.api.onliner.by',
        },
      });

      logger.info('Onliner API response received', { 
        status: response.status,
        hasData: !!response.data,
        dataKeys: response.data ? Object.keys(response.data) : [],
        apartmentsCount: response.data?.apartments?.length || 0
      });

      if (!response.data || !response.data.apartments || response.data.apartments.length === 0) {
        logger.warn('No apartments found in Onliner API', { url, apiUrl, responseData: JSON.stringify(response.data).substring(0, 500) });
        return [];
      }

      const ads: Ad[] = response.data.apartments.map((apt: any) => {
        // Проверка что id существует
        if (!apt.id) {
          logger.warn('Skipping ad without id', { apartment: apt });
          return null;
        }

        // Формируем заголовок из характеристик квартиры
        // Преобразуем rent_type в читаемый формат
        let rooms = '';
        if (apt.rent_type) {
          const rentTypeMap: Record<string, string> = {
            '1_room': '1-комнатная',
            '2_rooms': '2-комнатная',
            '3_rooms': '3-комнатная',
            '4_rooms': '4-комнатная',
            '5_rooms': '5-комнатная',
            '6_rooms': '6-комнатная',
            'studio': 'Студия',
          };
          rooms = rentTypeMap[apt.rent_type] || apt.rent_type;
        }
        
        const area = apt.area?.total ? `${apt.area.total} м²` : '';
        const floor = apt.floor ? `${apt.floor} этаж` : '';
        
        const titleParts = [rooms, area, floor].filter(Boolean);
        const title = titleParts.length > 0 ? titleParts.join(', ') : 'Квартира';
        
        // Цена: проверяем явно на null/undefined, чтобы 0 обрабатывался корректно
        let price = '';
        if (apt.price?.amount != null) {
          price = `${apt.price.amount} ${apt.price.currency}`;
        } else if (apt.price?.text) {
          // Fallback: если API возвращает готовый текст цены
          price = apt.price.text;
        }

        // URL может быть в apt.url или формируется из apt.id
        const adUrl = apt.url || `https://r.onliner.by/ak/apartments/${apt.id}`;
        // photo может быть строкой с URL или объектом { url }
        const imageUrl = typeof apt.photo === 'string' ? apt.photo : apt.photo?.url;
        
        // Извлекаем город и адрес
        // user_address обычно содержит полный адрес "Город, Улица, Дом"
        // address содержит то же самое
        const fullAddress = apt.location?.user_address || apt.location?.address || '';
        
        // Разделяем на город и адрес
        let location = '';
        let address = '';
        
        if (fullAddress) {
          const parts = fullAddress.split(',').map((p: string) => p.trim());
          if (parts.length > 0) {
            location = parts[0]; // Первая часть - город
            if (parts.length > 1) {
              address = parts.slice(1).join(', '); // Остальное - адрес
            }
          }
        }
        
        // Извлекаем дату публикации и обновления
        let publishedAt: Date | undefined;
        let updatedAt: Date | undefined;
        
        if (apt.created_at) {
          publishedAt = new Date(apt.created_at);
        }
        
        if (apt.last_time_up) {
          updatedAt = new Date(apt.last_time_up);
        }

        return {
          external_id: `onliner_realty_${apt.id}`,
          title,
          price,
          image_url: imageUrl,
          ad_url: adUrl,
          location: location || undefined,
          address: address || undefined,
          published_at: publishedAt,
          updated_at: updatedAt,
        };
      }).filter((ad: Ad | null): ad is Ad => ad !== null);

      // Сортируем объявления по дате создания (от новых к старым)
      ads.sort((a: Ad, b: Ad) => {
        const timeA = a.published_at ? a.published_at.getTime() : 0;
        const timeB = b.published_at ? b.published_at.getTime() : 0;
        return timeB - timeA;
      });

      logger.info('Onliner real estate API parsing successful', { url, adsCount: ads.length });
      return ads;
    } catch (error: any) {
      logger.error('Onliner real estate API parsing failed', { url, error: error.message });
      throw error;
    }
  }
}
