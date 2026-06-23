from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes


def check_admin(admin_ids: set[int]):
    def decorator(handler: Callable):
        @wraps(handler)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            if user is None or user.id not in admin_ids:
                message = update.effective_message
                if message is not None:
                    await message.reply_text("⛔ This command requires admin access.")
                return
            return await handler(update, context)

        return wrapper

    return decorator
