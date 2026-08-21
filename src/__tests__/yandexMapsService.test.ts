import axios from 'axios';
import { YandexMapsService } from '../services/YandexMapsService';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('YandexMapsService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('uses /v1 geocoder endpoint with lang', async () => {
    mockedAxios.get.mockResolvedValue({
      data: {
        response: {
          GeoObjectCollection: {
            featureMember: [
              {
                GeoObject: {
                  Point: { pos: '27.561831 53.902496' },
                  metaDataProperty: { GeocoderMetaData: { kind: 'house' } },
                },
              },
            ],
          },
        },
      },
    });

    const service = new YandexMapsService('geo-key');
    const result = await service.geocodeAddress('Минск, ул. Ленина 1');

    expect(mockedAxios.get).toHaveBeenCalledWith(
      'https://geocode-maps.yandex.ru/v1/',
      expect.objectContaining({
        params: expect.objectContaining({
          apikey: 'geo-key',
          geocode: 'Минск, ул. Ленина 1',
          lang: 'ru_RU',
          format: 'json',
        }),
      })
    );
    expect(result).toMatchObject({
      lon: 27.561831,
      lat: 53.902496,
      kind: 'house',
      bounds: undefined,
      envelope: undefined,
    });
    // timestamp установлен динамически
    expect(result?.timestamp).toBeDefined();
    expect(typeof result?.timestamp).toBe('number');
  });

  test('uses /v1 static maps endpoint with separate static key', () => {
    const service = new YandexMapsService('geo-key', 'static-key');

    const url = service.getStaticMapUrl(53.902496, 27.561831, 16);

    expect(url).toMatch(/^https:\/\/static-maps\.yandex\.ru\/v1\?/);
    expect(url).toContain('apikey=static-key');
    expect(url).toContain('ll=27.561831%2C53.902496');
    expect(url).toContain('z=16');
  });

  test('falls back to geocoder key for static maps when none provided', () => {
    const service = new YandexMapsService('geo-key');

    const url = service.getStaticMapUrl(53.902496, 27.561831);

    expect(url).toContain('apikey=geo-key');
  });

  test('extracts bounds envelope for locality results', async () => {
    mockedAxios.get.mockResolvedValue({
      data: {
        response: {
          GeoObjectCollection: {
            featureMember: [
              {
                GeoObject: {
                  Point: { pos: '27.561831 53.902496' },
                  metaDataProperty: { GeocoderMetaData: { kind: 'locality' } },
                  boundedBy: {
                    Envelope: {
                      lowerCorner: '27.452733 53.839145',
                      upperCorner: '27.692979 53.973499',
                    },
                  },
                },
              },
            ],
          },
        },
      },
    });

    const service = new YandexMapsService('geo-key');
    const result = await service.geocodeAddress('Минск');

    expect(result?.bounds).toEqual({
      lowerCorner: [27.452733, 53.839145],
      upperCorner: [27.692979, 53.973499],
    });
    expect(result?.envelope).toBe('27.452733,53.839145~27.692979,53.973499');
  });
});
