import { mapError } from '../utils/errorMapper';

describe('mapError', () => {
  test('maps DNS/connection failure', () => {
    expect(mapError({ code: 'ENOTFOUND' })).toContain('Не удалось подключиться к сайту');
    expect(mapError({ code: 'ECONNREFUSED' })).toContain('Не удалось подключиться к сайту');
  });

  test('maps HTTP 403', () => {
    expect(mapError({ response: { status: 403 } })).toContain('Доступ к сайту заблокирован');
  });

  test('maps HTTP 404', () => {
    expect(mapError({ response: { status: 404 } })).toContain('Страница не найдена');
  });

  test('maps HTTP 429', () => {
    expect(mapError({ response: { status: 429 } })).toContain('Слишком много запросов');
  });

  test('maps 5xx server errors', () => {
    expect(mapError({ response: { status: 500 } })).toContain('Сайт временно недоступен');
    expect(mapError({ response: { status: 503 } })).toContain('Сайт временно недоступен');
  });

  test('maps timeout', () => {
    expect(mapError({ message: 'timeout of 10000ms exceeded' })).toContain('Превышено время ожидания');
  });

  test('maps parse/JSON errors', () => {
    expect(mapError({ message: 'Unexpected token in JSON' })).toContain('Ошибка обработки данных');
    expect(mapError({ message: 'parse failed' })).toContain('Ошибка обработки данных');
  });

  test('falls back to generic message for unknown errors', () => {
    expect(mapError(new Error('something else'))).toContain('Произошла ошибка');
  });
});
