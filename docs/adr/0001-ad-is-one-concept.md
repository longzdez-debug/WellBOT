# Ad is one concept, not a parser/store split

Parsers return the same thing the store persists: a single classifieds listing. The code previously modelled them as two types (`AdData` for parser output, `Ad` for stored rows) and drifted — `Ad` was missing `location`/`address` that the database actually stores, forcing `(ad as any)` casts in `BotHandler`. We decided there is one domain concept, `Ad`, with only identity fields (`id`, `link_id`) added on save.
