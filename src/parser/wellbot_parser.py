"""WellBoT parser — fetches ads from WellBoT using JSON API."""

import asyncio
import logging
import json
import random
from typing import List

import aiohttp
from bs4 import BeautifulSoup

from src.parser.models import Ad
from src.core.config import config

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


class WellBoTParser:
    def __init__(self):
        self.retry_attempts = config.PARSER_RETRY_ATTEMPTS
        self.retry_delay = config.PARSER_RETRY_DELAY
        self.timeout = config.PARSER_TIMEOUT
        self._zero_results = False

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    async def fetch_ads(self, url: str) -> List[Ad]:
        """Fetch ads from WellBoT URL with retry logic."""
        ads: List[Ad] = []
        self._zero_results = False

        for attempt in range(1, self.retry_attempts + 1):
            try:
                async with aiohttp.ClientSession(headers=self._get_headers()) as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                        if response.status == 403:
                            logger.warning(f"WellBoTParser: 403 Forbidden (attempt {attempt}/{self.retry_attempts}) for {url}")
                            if attempt < self.retry_attempts:
                                await asyncio.sleep(self.retry_delay * attempt)
                                continue
                            return ads
                        if response.status != 200:
                            logger.warning(f"WellBoTParser: status {response.status} for {url}")
                            return ads
                        html = await response.text()

                ads = self._parse_html(html, url)
                if ads or attempt >= self.retry_attempts:
                    return ads
                if self._zero_results:
                    return ads
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay)

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(f"WellBoTParser network error (attempt {attempt}/{self.retry_attempts}) for {url}: {exc}")
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay * attempt)
                else:
                    logger.error(f"WellBoTParser: all retries exhausted for {url}")
                    return ads
            except Exception as exc:
                logger.exception(f"WellBoTParser failed parsing {url}: {exc}")
                return ads

        return ads

    async def fetch_ad_details(self, ad_url: str) -> dict:
        """Fetch description and seller name from individual ad page."""
        result = {"description": "", "seller": ""}
        try:
            async with aiohttp.ClientSession(headers=self._get_headers()) as session:
                async with session.get(ad_url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                    if response.status != 200:
                        return result
                    html = await response.text()

            soup = BeautifulSoup(html, "html.parser")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            if not script_tag:
                return result

            data = json.loads(script_tag.string)
            ad_data = data.get("props", {}).get("initialState", {}).get("adView", {}).get("data", {})
            result["description"] = ad_data.get("body", "") or ""
            result["seller"] = ad_data.get("userName", "") or ""
            return result
        except Exception as exc:
            logger.debug(f"fetch_ad_details failed for {ad_url}: {exc}")
            return result

    def _parse_html(self, html: str, url: str) -> List[Ad]:
        """Parse HTML response and extract ads."""
        ads: List[Ad] = []
        soup = BeautifulSoup(html, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__")

        if not script_tag:
            logger.error(f"Не удалось найти __NEXT_DATA__ на странице {url}")
            return ads

        try:
            data = json.loads(script_tag.string)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Ошибка парсинга JSON __NEXT_DATA__ для {url}: {e}")
            return ads

        # Universal search for listings in JSON structure
        listings = []

        # Primary path: props.initialState.listing.ads
        try:
            listings = data.get('props', {}).get('initialState', {}).get('listing', {}).get('ads', [])
        except Exception:
            pass

        # Fallback paths
        if not listings:
            try:
                listings = data.get('props', {}).get('pageProps', {}).get('initialStoreStates', {}).get('listings', {}).get('ads', [])
            except Exception:
                pass

            if not listings:
                try:
                    listings = data.get('props', {}).get('pageProps', {}).get('ads', [])
                except Exception:
                    pass

                if not listings:
                    total = 0
                    try:
                        raw_total = data.get('props', {}).get('initialState', {}).get('listing', {}).get('total', 0)
                        total = int(raw_total) if raw_total is not None else 0
                    except (ValueError, TypeError):
                        pass
                    if total == 0:
                        self._zero_results = True
                        logger.info(f"По запросу нет результатов (total=0): {url}")
                    else:
                        logger.warning(f"Объявления не найдены в JSON (total={total}) по адресу: {url}")
                    return ads

        for item in listings:
            try:
                if not item.get('ad_id'):
                    continue

                ad_id = str(item.get('ad_id'))
                link = item.get('ad_link', '')
                if not link:
                    continue

                # Price
                price_val = item.get('price_byn', '0')
                try:
                    price_float = float(price_val) / 100
                except (ValueError, TypeError):
                    price_float = 0.0

                price_text = f"{int(price_float)} р." if price_float > 0 else "Договорная"

                # Location
                region_item = ''
                area_item = ''
                for param in item.get('ad_parameters', []):
                    if not isinstance(param, dict):
                        continue
                    p_name = param.get('p', '')
                    if p_name == 'reg':
                        region_item = param.get('vl', '')
                    elif p_name in ('area', 'city'):
                        area_item = param.get('vl', '')
                if not region_item:
                    region_item = item.get('region_item', 'Беларусь')
                city = f"{area_item}, {region_item}" if area_item else region_item

                # Description and images
                description = item.get('body', 'Новое предложение на WellBoT')
                images = []
                for img in item.get('images', []):
                    path = img.get('path', '')
                    if path:
                        images.append(f"https://rms.kufar.by/v1/gallery/{path}")

                # Timestamp
                list_time = item.get('list_time', '')
                ad_id_int = 0
                try:
                    ad_id_int = int(ad_id)
                except (ValueError, TypeError):
                    pass

                ads.append(Ad(
                    id=ad_id,
                    title=item.get('subject', 'Объявление WellBoT'),
                    price=price_text,
                    url=link,
                    city=city,
                    description=description,
                    images=images,
                    list_time=list_time,
                    ad_id_int=ad_id_int
                ))
            except Exception as inner_e:
                logger.debug(f"Пропуск элемента из-за ошибки: {inner_e}")
                continue

        # Sort by ad_id descending (higher ID = more recently published)
        try:
            ads.sort(key=lambda a: a.ad_id_int, reverse=True)
        except Exception:
            pass

        return ads
