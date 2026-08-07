"""Data models for the bot."""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Ad:
    """Represents a WellBoT advertisement."""
    id: str = ""
    title: str = ""
    price: str = ""
    url: str = ""
    city: str = ""
    description: Optional[str] = None
    images: Optional[List[str]] = None
    list_time: str = ""
    seller: str = ""
    ad_id_int: int = 0


@dataclass
class SearchTask:
    """Represents a user's search task."""
    id: int
    user_id: int
    title: str
    url: str
    min_price: float
    max_price: float
    is_active: int = 1
    excluded_keywords: Optional[str] = None
    price_drop_threshold: float = 0.0
    only_photos: int = 0
    channel_id: Optional[int] = None