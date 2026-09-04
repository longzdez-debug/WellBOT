import axios from 'axios';
import { logger } from '../utils/logger';

export interface Coordinates {
  lat: number;
  lon: number;
}

/**
 * Геокодирование через Nominatim (OpenStreetMap).
 * Адрес -> координаты для нативной карточки Telegram (sendVenue).
 *
 * Адреса с Kufar приходят в виде "Район, Улица ул, Дом, Город" (location + address).
 * Свободный текстовый запрос (q=) ненадёжен: район в начале и суффиксы улиц
 * ("пр", "ул") сбивают поиск, возвращая объекты из других городов.
 * Поэтому используем structured-запрос (street=, city=): город берём из последней
 * части адреса, из улицы вырезаем суффиксы (ул/пр/пер/ш и т.п.).
 *
 * Политика Nominatim: макс. 1 запрос/сек, идентифицирующий User-Agent, кэшировать.
 */
export class LocationService {
  private nominatimUrl = 'https://nominatim.openstreetmap.org/search';
  private cache: Map<string, Coordinates | null> = new Map();
  private userAgent = 'WellBOT/1.0 (https://github.com/wellbot; contact: bot@wellbot.by)';
  private lastRequestAt = 0;
  private streetSuffixRe = /(^|[\s,])(ул|улица|пр|проспект|б-р|бульвар|пер|переулок|пл|площадь|ш|шоссе)\.?(?=[\s,]|$)/gu;

  /**
   * Адрес -> координаты. Пробует кандидатов по порядку (самый специфичный первый):
   * полный адрес без района -> адрес с районом -> район/город.
   * Возвращает null, если найти не удалось.
   */
  async getCoordinates(...candidates: Array<string | null | undefined>): Promise<Coordinates | null> {
    for (const candidate of candidates) {
      if (!candidate || !candidate.trim()) continue;
      const coords = await this.geocode(candidate);
      if (coords) return coords;
    }
    return null;
  }

  private async geocode(query: string): Promise<Coordinates | null> {
    const cacheKey = query.trim().toLowerCase();
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey) || null;
    }

    try {
      const params = this.buildParams(query);
      if (!params) {
        this.cache.set(cacheKey, null);
        return null;
      }

      await this.throttle();

      const response = await axios.get(this.nominatimUrl, {
        params: {
          ...params,
          format: 'json',
          limit: 1,
          countrycodes: 'by',
          'accept-language': 'ru',
        },
        headers: {
          'User-Agent': this.userAgent,
        },
        timeout: 5000,
      });

      const result = response.data?.[0];
      const coords = result && result.lat && result.lon
        ? { lat: parseFloat(result.lat), lon: parseFloat(result.lon) }
        : null;

      this.cache.set(cacheKey, coords);
      return coords;
    } catch (error: any) {
      logger.error('Geocoding error (Nominatim)', { query, error: error.message });
      this.cache.set(cacheKey, null);
      return null;
    }
  }

  /**
   * Разбивает адрес на street и city для structured-запроса Nominatim.
   * Город - последняя часть через запятую. Из улицы убираем суффиксы.
   * Если город не похож на город (короткий/без маркера города), отдаём q= свободно.
   */
  private buildParams(query: string): { street: string; city: string } | { q: string } | null {
    const parts = query.split(',').map(p => p.trim()).filter(Boolean);
    if (parts.length < 2) {
      return { q: query };
    }

    const city = parts[parts.length - 1];
    const streetRaw = parts.slice(0, parts.length - 1).join(', ');

    // Город должен быть одиночным словом/словосочетанием, а не улицей с номером дома.
    // Примеры: "Минск", "Витебск", "Минская область" - не подходит как город в адресе.
    const cityIsLikely = /^[\p{L}\s-]+$/u.test(city) && !/\d/.test(city);
    if (!cityIsLikely) {
      return { q: query };
    }

    const street = streetRaw
      .replace(this.streetSuffixRe, (_m, prefix: string) => prefix)
      .replace(/\s+/g, ' ')
      .replace(/\s+([,.])/g, '$1')
      .replace(/[,\s]+$/g, '')
      .trim();
    if (!street) {
      return { q: query };
    }

    return { street, city };
  }

  /** Ограничение ~1 запрос/сек по политике Nominatim. */
  private async throttle(): Promise<void> {
    const elapsed = Date.now() - this.lastRequestAt;
    if (elapsed < 1100) {
      await new Promise(resolve => setTimeout(resolve, 1100 - elapsed));
    }
    this.lastRequestAt = Date.now();
  }
}
