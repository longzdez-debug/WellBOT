export function mapError(error: any): string {
  if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
    return '❌ Не удалось подключиться к сайту. Проверьте интернет-соединение или попробуйте позже.';
  }

  const status = error.response?.status;

  if (status === 403) {
    return '❌ Доступ к сайту заблокирован. Попробуйте позже.';
  }

  if (status === 404) {
    return '❌ Страница не найдена. Проверьте правильность ссылки.';
  }

  if (status === 429) {
    return '❌ Слишком много запросов к сайту. Подождите немного и попробуйте снова.';
  }

  if (status >= 500) {
    return '❌ Сайт временно недоступен. Попробуйте позже.';
  }

  if (error.message?.includes('timeout')) {
    return '❌ Превышено время ожидания ответа от сайта. Попробуйте позже.';
  }

  if (error.message?.includes('parse') || error.message?.includes('JSON')) {
    return '❌ Ошибка обработки данных с сайта. Возможно, сайт изменил формат страницы.';
  }

  return '❌ Произошла ошибка. Попробуйте позже.';
}
