# Implementation Plan

## MVP - Minimum Viable Product (Core Functionality)

## 1. Project Setup and Infrastructure

- [ ] 1.1 Initialize new Node.js TypeScript project
  - Create package.json with dependencies: typescript, node-telegram-bot-api, pg, axios, cheerio, node-cron, dotenv
  - Configure tsconfig.json for strict mode
  - Set up folder structure: src/{bot, parsers, database, types, utils}
  - _Requirements: 7.1, 7.2_

- [ ] 1.2 Create Docker configuration
  - Write Dockerfile for Node.js application
  - Create docker-compose.yml with PostgreSQL and bot services
  - Add .env.example with TELEGRAM_BOT_TOKEN and DATABASE_URL
  - _Requirements: 7.1, 7.4_

- [ ] 1.3 Set up PostgreSQL database schema
  - Create migration script for users, links, ads tables
  - Add indexes for performance (telegram_id, external_id, is_active)
  - Implement auto-migration on startup
  - _Requirements: 7.3_

## 2. Database Layer

- [ ] 2.1 Implement DatabaseService class
  - Create connection pool with pg library
  - Implement auto-reconnect logic
  - Add transaction support
  - _Requirements: 6.4_

- [ ] 2.2 Implement User operations
  - createUser(telegramId, username)
  - getUser(telegramId)
  - _Requirements: 1.2_

- [ ] 2.3 Implement Link operations
  - createLink(userId, url, platform)
  - getUserLinks(userId)
  - deleteLink(linkId)
  - getActiveLinks()
  - incrementErrorCount(linkId)
  - markLinkInactive(linkId)
  - _Requirements: 2.5, 5.3, 3.5_

- [ ] 2.4 Implement Ad operations
  - createAd(linkId, adData)
  - getAdByExternalId(externalId)
  - isNewAd(externalId)
  - _Requirements: 3.2, 4.5_

## 3. Telegram Bot Handlers

- [ ] 3.1 Initialize Telegram bot
  - Set up node-telegram-bot-api with polling
  - Configure error handling for Telegram API
  - _Requirements: 6.3_

- [ ] 3.2 Implement /start command
  - Auto-register user on /start
  - Save telegram_id and username to database
  - Display main menu with inline keyboard: "Добавить ссылку", "Мои ссылки"
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 3.3 Implement "Добавить ссылку" flow
  - Handle "Добавить ссылку" button click
  - Request URL from user
  - Validate URL and detect platform (Kufar/Onliner/Realt)
  - Check user hasn't exceeded 10 links limit
  - Save link to database
  - Show success/error message
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [ ] 3.4 Implement "Мои ссылки" flow
  - Handle "Мои ссылки" button click
  - Fetch user's links from database
  - Display list with platform icons and URLs
  - Add "Удалить" button for each link
  - _Requirements: 2.1, 5.1_

- [ ] 3.5 Implement link deletion
  - Handle "Удалить" button click
  - Delete link from database
  - Show confirmation message
  - _Requirements: 5.2, 5.3_

- [ ] 3.6 Implement notification sender
  - sendNotification(chatId, ad) method
  - Send photo + caption if image_url exists
  - Send text message if no image
  - Format message: title, price, link
  - Handle blocked users gracefully
  - _Requirements: 4.1, 4.2, 4.3_

## 4. Parser Implementation

- [ ] 4.1 Create base Parser interface
  - Define IParser interface with parseUrl() and validateUrl()
  - Create abstract BaseParser class with common logic
  - Implement retry mechanism with exponential backoff
  - Add User-Agent rotation
  - _Requirements: 3.1, 6.5_

- [ ] 4.2 Implement KufarParser
  - Validate URL pattern: https://kufar.by/l/*
  - Fetch HTML with axios
  - Parse JSON from window.__INITIAL_STATE__ using cheerio
  - Extract ads: external_id, title, price, image_url, ad_url
  - Return array of AdData
  - _Requirements: 2.3, 2.4, 3.2, 3.3_

- [ ] 4.3 Implement OnlinerParser
  - Validate URL pattern: https://baraholka.onliner.by/* or https://ab.onliner.by/*
  - Fetch and parse HTML structure
  - Extract ads from HTML elements or JSON
  - Map to AdData format
  - _Requirements: 2.3, 2.4, 3.2, 3.3_

- [ ] 4.4 Implement RealtParser
  - Validate URL pattern: https://realt.by/*
  - Fetch and parse HTML
  - Extract ads from page structure
  - Map to AdData format
  - _Requirements: 2.3, 2.4, 3.2, 3.3_

- [ ] 4.5 Implement ParserFactory
  - Create factory to get correct parser by platform
  - Handle unknown platforms gracefully
  - _Requirements: 2.3_

## 5. Parsing Scheduler

- [ ] 5.1 Implement ParserScheduler class
  - Set up node-cron to run every minute: '* * * * *'
  - Fetch all active links from database
  - Group links by platform for efficient processing
  - _Requirements: 3.1_

- [ ] 5.2 Implement parallel parsing logic
  - Parse links in parallel with Promise.all
  - Limit concurrent requests to 10
  - Handle individual link failures without stopping others
  - _Requirements: 6.2_

- [ ] 5.3 Implement new ad detection and notification
  - For each parsed ad, check if it's new (isNewAd)
  - If new, save to database (createAd)
  - Send notification to user (sendNotification)
  - Group notifications (max 1 per minute per link)
  - _Requirements: 3.2, 4.1, 4.4, 4.5_

- [ ] 5.4 Implement error handling for failed parses
  - Increment error_count on parse failure
  - Mark link as inactive if error_count >= 5
  - Log all errors for debugging
  - _Requirements: 3.5, 6.5_

## 6. Utilities and Helpers

- [ ] 6.1 Create Logger utility
  - Implement structured logging (info, warn, error)
  - Log to console with timestamps
  - Include context (linkId, platform, userId)
  - _Requirements: 6.5_

- [ ] 6.2 Create URL validator utility
  - Validate URL format
  - Detect platform from domain
  - Return platform type or null
  - _Requirements: 2.4_

- [ ] 6.3 Create rate limiter for bot commands
  - Limit user to 10 commands per minute
  - Prevent spam and abuse
  - _Requirements: 6.3_

## 7. Deployment

- [ ] 7.1 Create startup script
  - Run database migrations
  - Initialize bot
  - Start parser scheduler
  - Handle graceful shutdown
  - _Requirements: 7.1, 7.3_

- [ ] 7.2 Create README with setup instructions
  - Document environment variables
  - Provide docker-compose up command
  - Add example .env file
  - Include troubleshooting section
  - _Requirements: 7.1, 7.2_

---

## POST-MVP - Testing and Optimization (Future Enhancements)

### Testing

- [ ]* 8.1 Write database migration tests
  - Test schema creation
  - Test indexes creation
  - Verify constraints
  - _Requirements: 7.3_

- [ ]* 8.2 Test bot command flows
  - Test /start registration
  - Test add link flow with valid/invalid URLs
  - Test my links display
  - Test link deletion
  - _Requirements: 1.1, 2.1, 5.1_

- [ ]* 8.3 Test parsers with real URLs
  - Test KufarParser with sample Kufar URL
  - Test OnlinerParser with sample Onliner URL
  - Test RealtParser with sample Realt URL
  - Verify extracted data format
  - _Requirements: 3.2, 3.3_

### Optimization

- [ ]* 9.1 Implement old ads cleanup job
  - Schedule daily cleanup at 3 AM: '0 3 * * *'
  - Delete ads older than 30 days
  - Log cleanup statistics
  - _Requirements: 6.1_

- [ ]* 9.2 Add database connection pooling
  - Configure pool size to 10 connections
  - Implement connection health checks
  - _Requirements: 6.1, 6.4_

- [ ]* 9.3 Optimize parser performance
  - Add 1 second delay between requests
  - Implement request timeout (10 seconds)
  - Parse only first page of results (last 20-30 ads)
  - _Requirements: 6.2_
