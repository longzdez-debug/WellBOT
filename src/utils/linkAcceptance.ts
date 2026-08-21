import { Platform } from '../types';

export interface AssessmentResult {
  platform: Platform | null;
  ok: boolean;
  reason?: string;
}

export class LinkAcceptance {
  static assess(url: string): AssessmentResult {
    let urlObj: URL;
    try {
      urlObj = new URL(url);
    } catch {
      return { platform: null, ok: false, reason: 'Некорректный URL' };
    }

    const hostname = urlObj.hostname.toLowerCase();
    const pathname = urlObj.pathname;

    if (hostname.includes('kufar.by')) {
      if (pathname.startsWith('/l/') || pathname.startsWith('/re/')) {
        return { platform: 'kufar', ok: true };
      }
      return { platform: 'kufar', ok: false, reason: 'Это ссылка на конкретное объявление. Нужна ссылка на страницу поиска с фильтрами.' };
    }

    if (hostname.includes('onliner.by')) {
      // Проверяем поддомены baraholka, ab, r.onliner
      if (hostname === 'baraholka.onliner.by' || hostname === 'ab.onliner.by' || hostname.includes('r.onliner')) {
        return { platform: 'onliner', ok: true };
      }
      return { platform: 'onliner', ok: false, reason: 'Нужна ссылка на Барахолку, Авто или Недвижимость Onliner.' };
    }

    if (hostname.includes('av.by')) {
      // av.by — только страницы cars.av.by
      if (hostname === 'cars.av.by' || hostname === 'www.cars.av.by' || hostname === 'av.by') {
        return { platform: 'av', ok: true };
      }
      return { platform: 'av', ok: false, reason: 'Нужна ссылка на страницу поиска автомобилей (cars.av.by).' };
    }

    return { platform: null, ok: false, reason: 'Неподдерживаемая площадка' };
  }
}
