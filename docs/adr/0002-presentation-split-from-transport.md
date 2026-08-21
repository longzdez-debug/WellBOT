# AdPresenter formats, TelegramSender transports

`BotHandler` duplicated ad-to-message formatting verbatim (`sendAdWithMap` and `sendNotification`) and error-to-message mapping five times. We split presentation from transport: a pure `AdPresenter` with interface `format(ad) → { text, media[] }` builds what the user sees, a separate `TelegramSender` performs `sendMessage`/`sendMediaGroup` with the photo fallback and the inter-send pacing delay. `BotHandler` shrinks to routing and state; presentation stays testable without Telegram.
