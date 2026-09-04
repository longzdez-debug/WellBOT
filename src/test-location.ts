import 'dotenv/config';
import { KufarParser } from './parsers/KufarParser';
import { LocationService } from './services/LocationService';

const DEFAULT_URLS = [
  'https://re.kufar.by/l/minsk/snyat/kvartiru/bez-posrednikov',
  'https://www.kufar.by/l/r~minsk/muzykalnye-instrumenty',
];

export async function runLocationTest(urls: string[] = DEFAULT_URLS): Promise<void> {
  console.log('--- ТЕСТ LocationService на реальных объявлениях Kufar ---');

  const parser = new KufarParser();
  const locationService = new LocationService();

  for (const url of urls) {
    console.log(`\n--- Тестируем: ${url} ---`);
    try {
      const ads = await parser.parseUrl(url);
      console.log(`Найдено объявлений: ${ads.length}`);

      const sample = ads.slice(0, 5);
      for (const ad of sample) {
        const addressParts = [ad.location, ad.address].filter(Boolean);
        const fullAddress = addressParts.join(', ');
        console.log(`\n📌 "${ad.title}"`);
        console.log(`   location="${ad.location || ''}" address="${ad.address || ''}"`);
        if (!fullAddress) {
          console.log('   ⏭ пропуск (нет адреса)');
          continue;
        }
        const coords = await locationService.getCoordinates(ad.address, fullAddress, ad.location);
        if (coords) {
          console.log(`   ✅ Координаты: ${coords.lat}, ${coords.lon}`);
          console.log(`      OSM: https://www.openstreetmap.org/?mlat=${coords.lat}&mlon=${coords.lon}#map=16/${coords.lat}/${coords.lon}`);
        } else {
          console.log('   ❌ Не найдено');
        }
      }
    } catch (error: any) {
      console.error(`Ошибка: ${error.message}`);
    }
  }

  console.log('\n--- ТЕСТ ЗАВЕРШЁН ---');
}

// CLI: npx ts-node src/test-location.ts <url1> <url2> ...
if (require.main === module) {
  const urls = process.argv.slice(2);
  runLocationTest(urls.length > 0 ? urls : DEFAULT_URLS);
}
