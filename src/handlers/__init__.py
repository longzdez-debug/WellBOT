# Handlers package — imports register all sub-routers
from .common import router, set_database, get_db
from . import user, admin, payment, new_features, support, shop

__all__ = ["router", "set_database", "get_db"]
