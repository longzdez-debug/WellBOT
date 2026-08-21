# WellBOT

Telegram бот-парсер для отслеживания новых объявлений на белорусских площадках (Kufar.by, Onliner.by, Av.by).

WellBOT предоставляет простой способ получать уведомления о новых объявлениях по заданным пользователем ссылкам с фильтрами.

## Возможности

- 🟢 Отслеживание объявлений на Kufar.by
- 🔵 Отслеживание объявлений на Onliner.by (Барахолка и Авто)
- 🟠 Отслеживание объявлений на Av.by
- 📢 Уведомления о новых объявлениях в реальном времени
- 👤 Поддержка до 10 активных ссылок на пользователя
- 🎯 Простое управление ссылками через Telegram

## Технологии

- Node.js 20+ / TypeScript
- Telegram Bot API (node-telegram-bot-api)
- PostgreSQL 16
- Docker & Docker Compose
- Axios, Cheerio, node-cron

## Быстрый старт

### Требования

- Docker и Docker Compose
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))

### Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/wellbot/wellbot.git
cd wellbot
```

2. Создайте `.env` файл:
```bash
cp .env.example .env
```

3. Отредактируйте `.env` и добавьте ваш токен:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
DB_PASSWORD=your_secure_password
```

4. Запустите бота:
```bash
docker-compose up -d
```

> **Важно:** Бот автоматически запускает парсинг сразу после добавления ссылки, и затем проверяет объявления каждые 60 секунд (настраивается через `PARSE_INTERVAL_SECONDS`).

Бот автоматически создаст необходимые таблицы в базе данных при первом запуске.

### Локальная разработка

1. Установите зависимости:
```bash
npm install
```

2. Создайте `.env` файл с настройками

3. Запустите PostgreSQL (или используйте docker-compose только для БД):
```bash
docker-compose up -d postgres
```

4. Запустите бота в режиме разработки:
```bash
npm run dev
```

## Использование

1. Найдите вашего бота в Telegram и отправьте `/start`
2. Нажмите "➕ Добавить ссылку"
3. Отправьте ссылку на страницу с фильтрами (например, `https://kufar.by/l/minsk/...`)
4. Получайте уведомления о новых объявлениях!

### Поддерживаемые форматы ссылок

- **Kufar**: `https://kufar.by/l/*`
- **Onliner**: `https://baraholka.onliner.by/*` или `https://ab.onliner.by/*`
- **Realt**: `https://realt.by/*`

## Архитектура

```
src/
├── bot/              # Telegram bot handlers
├── database/         # Database service and schema
├── parsers/          # Platform parsers (Kufar, Onliner, Realt)
├── scheduler/        # Cron scheduler for parsing
├── types/            # TypeScript types
├── utils/            # Utilities (logger, validator, rate limiter)
└── index.ts          # Entry point
```

## Мониторинг

Просмотр логов:
```bash
docker-compose logs -f bot
```

Проверка статуса:
```bash
docker-compose ps
```

## Остановка

```bash
docker-compose down
```

Для удаления данных:
```bash
docker-compose down -v
```

## Документация

- [Requirements](.kiro/specs/wellbot/requirements.md) - Требования к проекту
- [Design](.kiro/specs/wellbot/design.md) - Архитектура и дизайн
- [Tasks](.kiro/specs/wellbot/tasks.md) - План реализации

## Troubleshooting

### Бот не отвечает
- Проверьте правильность `TELEGRAM_BOT_TOKEN` в `.env`
- Убедитесь, что контейнер запущен: `docker-compose ps`
- Проверьте логи: `docker-compose logs bot`

### Не приходят уведомления
- Проверьте, что ссылка активна (команда "Мои ссылки")
- Убедитесь, что парсер работает: `docker-compose logs bot | grep "Parsing"`
- Проверьте, что на странице есть новые объявления

### Ошибки подключения к БД
- Убедитесь, что PostgreSQL запущен: `docker-compose ps postgres`
- Проверьте `DATABASE_URL` в `.env`

## Лицензия

MIT
