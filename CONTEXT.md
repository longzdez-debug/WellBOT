# Kufar Enjoyer Bot

Telegram bot that tracks classified ads across Kufar, Onliner and av.by, notifying users when new listings appear for a search they follow.

## Language

**Ad**:
A single listing on a classifieds platform (one product, apartment, vehicle). One concept through its whole life: what a parser returns and what a store persists are the same thing — only identity fields (`id`, `link_id`) are added on save.
_Avoid_: AdData, listing-row, raw-ad

**SearchSubscription**:
A user's standing interest in a search page — the tracked URL (with filters) for which the bot reports new ads. In code and the database this is still called `Link`; the code name is a technical label, the domain concept is the subscription.
_Avoid_: link (when meaning the subscription), search-query, filter

**Platform**:
One of the three classifieds sites the bot tracks: kufar, onliner, av. Every ad and every search page belongs to exactly one platform, and each platform has its own URL shape.
_Avoid_: site, source, marketplace

**Search page**:
A platform URL that lists many ads for a search (with filters) — the thing a user subscribes to. Distinct from a page for a single ad, which is not subscribable.
_Avoid_: listing page, category page, filters page

**Parsing cycle**:
One scheduled pass over all active search subscriptions, fetching each, storing new ads, and deciding which the user sees.
_Avoid_: scan, run, iteration

**New ad**:
An ad whose `external_id` is not yet known for a given search subscription. Known ads are ignored; new ads may be shown to the user.
_Avoid_: fresh ad, unseen ad, unique ad
