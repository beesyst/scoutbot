from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_target_actions_keyboard(target_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Pause", callback_data=f"target:pause:{target_id}"
                ),
                InlineKeyboardButton(
                    "Resume", callback_data=f"target:resume:{target_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Delete", callback_data=f"target:delete:{target_id}"
                ),
                InlineKeyboardButton(
                    "Mark as noise", callback_data=f"target:noise:{target_id}"
                ),
            ],
        ]
    )
