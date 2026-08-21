# Design Document

## Overview

KufarEnjoyer_bot - минималистичный Telegram бот для парсинга объявлений с трех белорусских площадок. Архитектура построена на принципе простоты: один Node.js процесс, PostgreSQL для данных, без лишних зависимостей.

## Architecture

### High-Level Architecture

```
┌─────────────┐
│  Telegram   │
│   Users     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│      Telegram Bot API           │
│  (node-telegram-bot-api)        │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│      Bot Application            │
│  ┌───────────────────────────┐  │
│  │  Command Handlers         │  │
│  │  - /start                 │  │
│  │  - Добавить ссылку        │  │
│  │  - Мои ссылки             │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Parser Scheduler         │  │
│  │  (node-cron: */1 * * * *) │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Parsers                  │  │
│  │  - KufarParser            │  │
│  │  - OnlinerParser          │  │
│  │  - RealtParser            │  │
│  └───────────────────────────┘  │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│      PostgreSQL Database        │
│  - users                        │
│  - links                        │
│  - ads                          │
└─────────────────────────────────┘
```

### Technology Stack

- **Runtime**: Node.js 20+
- **Language**: TypeScript
- **Bot Framework**: node-telegram-bot-api
- **Database**: PostgreSQL 16
- **ORM**: pg (native PostgreSQL driver)
- **Scheduler**: node-cron
- **HTTP Client**: axios
- **HTML Parser**: cheerio
- **Container**: Docker + Docker Compose

## Components and Interfaces

### 1. Bot Handler

**Responsibilities:**
- Обработка команд пользователя
- Управление состоянием диалога
- Отправка уведомлений

**Key Methods:**
```typescript
class BotHandler {
  handleStart(chatId: number): Promise<void>
  handleAddLink(chatId: number, url: string): Promise<void>
  handleMyLinks(chatId: number): Promise<void>
  handleDeleteLink(chatId: number, linkId: number): Promise<void>
  sendNotification(chatId: number, ad: Ad): Promise<void>
}
```

### 2. Parser Scheduler

**Responsibilities:**
- Запуск парсинга каждую минуту
- Получение списка активных ссылок
- Распределение работы между парсерами

**Key Methods:**
```typescript
class ParserScheduler {
  start(): void
  async runParsing(): Promise<void>
  async getActiveLinks(): Promise<Link[]>
}
```

### 3. Platform Parsers

**Responsibilities:**
- Извлечение объявлений с конкретной площадки
- Определение новых объявлений
- Обработка ошибок парсинга

**Interface:**
```typescript
interface IParser {
  platform: 'kufar' | 'onliner' | 'realt'
  parseUrl(url: string): Promise<Ad[]>
  validateUrl(url: string): boolean
}

class KufarParser implements IParser {
  platform = 'kufar'
  async parseUrl(url: string): Promise<Ad[]>
  validateUrl(url: string): boolean
}

class OnlinerParser implements IParser {
  platform = 'onliner'
  async parseUrl(url: string): Promise<Ad[]>
  validateUrl(url: string): boolean
}

class RealtParser implements IParser {
  platform = 'realt'
  async parseUrl(url: string): Promise<Ad[]>
  validateUrl(url: string): boolean
}
```

### 4. Database Service

**Responsibilities:**
- CRUD операции с пользователями, ссылками, объявлениями
- Управление транзакциями
- Миграции схемы

**Key Methods:**
```typescript
class DatabaseService {
  // Users
  async createUser(telegramId: number, username: string): Promise<User>
  async getUser(telegramId: number): Promise<User | null>
  
  // Links
  async createLink(userId: number, url: string, platform: string): Promise<Link>
  async getUserLinks(userId: number): Promise<Link[]>
  async deleteLink(linkId: number): Promise<void>
  async getActiveLinks(): Promise<Link[]>
  async incrementErrorCount(linkId: number): Promise<void>
  async markLinkInactive(linkId: number): Promise<void>
  
  // Ads
  async createAd(linkId: number, ad: AdData): Promise<Ad>
  async getAdByExternalId(externalId: string): Promise<Ad | null>
  async isNewAd(externalId: string): Promise<boolean>
}
```

## Data Models

### PostgreSQL Schema

```sql
-- Users table
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Links table
CREATE TABLE links (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  platform VARCHAR(50) NOT NULL, -- 'kufar', 'onliner', 'realt'
  is_active BOOLEAN DEFAULT true,
  error_count INTEGER DEFAULT 0,
  last_parsed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT check_platform CHECK (platform IN ('kufar', 'onliner', 'realt'))
);

CREATE INDEX idx_links_user_id ON links(user_id);
CREATE INDEX idx_links_active ON links(is_active) WHERE is_active = true;

-- Ads table
CREATE TABLE ads (
  id SERIAL PRIMARY KEY,
  link_id INTEGER REFERENCES links(id) ON DELETE CASCADE,
  external_id VARCHAR(255) UNIQUE NOT NULL, -- ID объявления на площадке
  title TEXT NOT NULL,
  description TEXT,
  price VARCHAR(100),
  image_url TEXT,
  ad_url TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ads_link_id ON ads(link_id);
CREATE INDEX idx_ads_external_id ON ads(external_id);
CREATE INDEX idx_ads_created_at ON ads(created_at);
```

### TypeScript Types

```typescript
interface User {
  id: number
  telegram_id: number
  username: string | null
  created_at: Date
}

interface Link {
  id: number
  user_id: number
  url: string
  platform: 'kufar' | 'onliner' | 'realt'
  is_active: boolean
  error_count: number
  last_parsed_at: Date | null
  created_at: Date
}

interface Ad {
  id: number
  link_id: number
  external_id: string
  title: string
  description: string | null
  price: string | null
  image_url: string | null
  ad_url: string
  created_at: Date
}

interface AdData {
  external_id: string
  title: string
  description?: string
  price?: string
  image_url?: string
  ad_url: string
}
```

## Parser Implementation Details

### Kufar Parser

**URL Pattern:** `https://kufar.by/l/*`

**Parsing Strategy:**
1. Fetch HTML страницы с помощью axios
2. Парсинг HTML с помощью cheerio
3. Извлечение списка объявлений из JSON в `<script>` теге (window.__INITIAL_STATE__)
4. Маппинг данных в AdData

**Key Fields:**
- external_id: `ad.ad_id`
- title: `ad.subject`
- price: `ad.price_byn`
- image_url: `ad.images[0].path`
- ad_url: `https://kufar.by/item/${ad.ad_id}`

### Onliner Parser

**URL Pattern:** `https://baraholka.onliner.by/*` или `https://ab.onliner.by/*`

**Parsing Strategy:**
1. Fetch HTML страницы
2. Парсинг списка объявлений из HTML структуры
3. Извлечение данных из data-атрибутов или JSON

**Key Fields:**
- external_id: извлекается из URL или data-id
- title: текст заголовка
- price: цена из элемента
- image_url: src изображения
- ad_url: полная ссылка на объявление

### Realt Parser

**URL Pattern:** `https://realt.by/*`

**Parsing Strategy:**
1. Fetch HTML страницы
2. Парсинг списка объявлений
3. Извлечение данных из структуры HTML

**Key Fields:**
- external_id: ID из URL или data-атрибута
- title: заголовок объявления
- price: цена
- image_url: изображение
- ad_url: ссылка на объявление

## Error Handling

### Parser Errors

1. **Network Errors** (timeout, connection refused):
   - Retry 3 раза с экспоненциальной задержкой
   - Если все попытки неудачны - increment error_count

2. **Parsing Errors** (изменение структуры сайта):
   - Логирование ошибки
   - Increment error_count
   - Если error_count >= 5 - mark link as inactive

3. **Rate Limiting**:
   - Задержка между запросами: 1 секунда
   - User-Agent rotation
   - Если получен 429 - exponential backoff

### Bot Errors

1. **Telegram API Errors**:
   - Retry отправки сообщения 3 раза
   - Если пользователь заблокировал бота - mark user as inactive

2. **Database Errors**:
   - Автоматический reconnect
   - Transaction rollback при ошибках

## Testing Strategy

### Unit Tests

- Parser URL validation
- Data extraction from HTML
- Database CRUD operations
- Bot command handlers

### Integration Tests

- End-to-end парсинг реальных страниц (с моками)
- Database migrations
- Bot workflow (add link -> parse -> notify)

### Manual Testing

- Тестирование на реальных ссылках с каждой площадки
- Проверка уведомлений в Telegram
- Нагрузочное тестирование (100+ ссылок)

## Deployment

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: kufar_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  bot:
    build: .
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      DATABASE_URL: postgresql://bot_user:${DB_PASSWORD}@postgres:5432/kufar_bot
      NODE_ENV: production
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
```

### Environment Variables

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
DB_PASSWORD=secure_password_here

# Optional
NODE_ENV=production
LOG_LEVEL=info
```

### Dockerfile

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

CMD ["node", "dist/index.js"]
```

## Performance Considerations

### Parsing Optimization

1. **Parallel Parsing**: Парсинг ссылок параллельно (Promise.all) с лимитом 10 одновременных запросов
2. **Caching**: Кэширование HTML страниц на 30 секунд (в памяти)
3. **Incremental Updates**: Парсинг только первой страницы результатов (последние 20-30 объявлений)

### Database Optimization

1. **Indexes**: Индексы на часто используемые поля (telegram_id, external_id, is_active)
2. **Connection Pooling**: Пул из 10 соединений
3. **Batch Inserts**: Вставка новых объявлений батчами

### Memory Management

1. **Limit Ad History**: Хранить объявления только за последние 30 дней
2. **Cleanup Job**: Ежедневная очистка старых объявлений (cron: 0 3 * * *)

## Security

1. **SQL Injection**: Использование параметризованных запросов
2. **Rate Limiting**: Ограничение количества запросов от одного пользователя (10 команд в минуту)
3. **Input Validation**: Валидация всех URL перед сохранением
4. **Environment Variables**: Все секреты в .env файле (не в коде)

## Monitoring and Logging

### Logging

```typescript
// Structured logging
logger.info('Parsing started', { linkId, platform, url })
logger.error('Parsing failed', { linkId, error: err.message, stack: err.stack })
logger.warn('Link marked inactive', { linkId, errorCount })
```

### Metrics

- Количество активных пользователей
- Количество активных ссылок по площадкам
- Количество новых объявлений в час
- Процент успешных парсингов
- Среднее время парсинга

## Future Enhancements (Out of Scope for MVP)

- Фильтры по цене/региону прямо в боте
- Уведомления только в определенное время
- Экспорт объявлений в Excel
- Статистика по объявлениям
- Webhook вместо polling для Telegram
