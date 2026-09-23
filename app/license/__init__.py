"""MA-MinSight License subsystem."""

from app.license.edition import is_community_edition, read_edition
from app.license.manager import Manager, get_manager

__all__ = ["Manager", "get_manager", "is_community_edition", "read_edition"]
