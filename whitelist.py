import logging
from telegram import Update
from telegram.ext import filters

import config

logger = logging.getLogger(__name__)


class WhitelistFilter(filters.MessageFilter):
    def filter(self, message) -> bool:
        if message.from_user is None:
            return False
        user_id = message.from_user.id
        in_whitelist = user_id in config.ALLOWED_USER_IDS
        if not in_whitelist:
            logger.info(
                "Blocked unauthorized user: %s (id=%d)",
                message.from_user.full_name,
                user_id,
            )
        return in_whitelist


whitelist = WhitelistFilter()