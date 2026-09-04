import { Ad } from '../types';

export class NewAdSelector {
  private static toTime(date: Date | string | null | undefined): number {
    if (!date) return 0;
    const d = date instanceof Date ? date : new Date(date);
    return isNaN(d.getTime()) ? 0 : d.getTime();
  }

  static pick(ads: Ad[], limit: number): Ad[] {
    const sorted = [...ads].sort((a, b) => {
      const timeA = this.toTime(a.updated_at) || this.toTime(a.published_at);
      const timeB = this.toTime(b.updated_at) || this.toTime(b.published_at);

      if (timeB !== timeA) {
        return timeB - timeA; // новые первыми
      }

      // Если время одинаковое — сортируем по external_id (строка), преобразуя в число
      const idA = parseInt(String(a.external_id), 10) || 0;
      const idB = parseInt(String(b.external_id), 10) || 0;
      return idB - idA;
    });

    return sorted.slice(0, limit);
  }
}
