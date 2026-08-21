import { Ad } from '../types';
import { LocationService } from './LocationService';

export interface FormattedAd {
  text: string;
  media: string[];
  location?: { lat: number; lon: number; title: string; address: string };
}

export class AdPresenter {
  private locationService: LocationService | null;

  constructor(locationService: LocationService | null = null) {
    this.locationService = locationService;
  }

  // Экранирование HTML-символов для безопасного отображения в Telegram HTML
  private escapeHtml(str: string): string {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async format(ad: Ad): Promise<FormattedAd> {
    let message = `${this.escapeHtml(ad.title)}\n💰 ${this.escapeHtml(ad.price || 'Договорная')}`;

    if (ad.description) {
      // Ограничиваем описание ~2000 символами (Telegram лимит — 4096)
      const desc = ad.description.length > 2000 ? ad.description.substring(0, 2000) + '...' : ad.description;
      message += `\n${this.escapeHtml(desc)}`;
    }

    if (ad.published_at) {
      const publishedDate = ad.published_at instanceof Date ? ad.published_at : new Date(ad.published_at);
      if (!isNaN(publishedDate.getTime())) {
        const formattedPublished = publishedDate.toLocaleString('ru-RU', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          timeZone: 'Europe/Minsk',
        });

        if (ad.updated_at) {
          const updatedDate = ad.updated_at instanceof Date ? ad.updated_at : new Date(ad.updated_at);
          const timeDiff = updatedDate.getTime() - publishedDate.getTime();
          const daysDiff = Math.floor(timeDiff / (1000 * 60 * 60 * 24));

          if (daysDiff > 1) {
            const formattedUpdated = updatedDate.toLocaleString('ru-RU', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              timeZone: 'Europe/Minsk',
            });
            message += `\n🕐 Опубликовано: ${formattedPublished}`;
            message += `\n🔄 Поднято: ${formattedUpdated}`;
          } else {
            message += `\n🕐 ${formattedPublished}`;
          }
        } else {
          message += `\n🕐 ${formattedPublished}`;
        }
      }
    }

    const addressParts = [];
    if (ad.location) addressParts.push(this.escapeHtml(ad.location));
    if (ad.address) addressParts.push(this.escapeHtml(ad.address));
    const fullAddress = addressParts.join(', ');
    if (addressParts.length > 0) {
      message += `\n📍 ${fullAddress}`;
    }

    message += `\n🔗 ${this.escapeHtml(ad.ad_url)}`;

    const media: string[] = [];
    let location: FormattedAd['location'];

    if (ad.image_url) {
      media.push(ad.image_url);
    }

    // Карта отключена — Yandex Maps API запросы замедляют отправку уведомлений.
    // Если нужен адрес, он уже отображается в тексте.
    // if (fullAddress && this.yandexMaps) {
    //   try {
    //     const mapUrl = await this.yandexMaps.getMapForAddress(fullAddress);
    //     if (mapUrl) {
    //       media.push(mapUrl);
    //     }
    //   } catch {
    //     // Map generation failed, continue without map
    //   }
    // }

    if (fullAddress && this.locationService) {
      try {
        const coords = await this.locationService.getCoordinates(ad.address, fullAddress, ad.location);
        if (coords) {
          location = {
            lat: coords.lat,
            lon: coords.lon,
            title: ad.title,
            address: fullAddress,
          };
        }
      } catch {
        // Geocoding failed, continue without location
      }
    }

    return { text: message, media, location };
  }
}
