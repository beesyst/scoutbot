from __future__ import annotations

import logging
from typing import Any

from telegram import Message, Update
from telegram.ext import ContextTypes

from scoutbot_module.bot.formatters import (
    format_add_result,
    format_projects_list,
    format_targets_list,
)
from scoutbot_module.bot.keyboards import build_target_actions_keyboard
from scoutbot_module.changedetection.sync import run_sync
from scoutbot_module.core.paths import resolve_project_path
from scoutbot_module.db.session import create_db_engine, get_session
from scoutbot_module.discovery.urls import normalize_url, validate_url
from scoutbot_module.services.targets import add_target

LOG = logging.getLogger("scoutbot.bot.handlers")


async def _reply(update: Update, text: str, **kwargs: Any) -> None:
    message = update.effective_message
    if message is None:
        LOG.warning("Telegram update has no effective message")
        return
    await message.reply_text(text, **kwargs)


async def _safe_callback_reply(
    update: Update,
    text: str,
    **kwargs: Any,
) -> None:
    query = update.callback_query
    if query is None:
        return

    try:
        await query.edit_message_text(text, **kwargs)
        return
    except Exception:
        LOG.warning("Failed to edit callback message")

    message = query.message
    if isinstance(message, Message):
        try:
            await message.reply_text(text, **kwargs)
        except Exception:
            LOG.warning("Failed to send callback fallback reply")
    else:
        LOG.warning("Callback message is inaccessible; fallback reply skipped")


async def _sync_after_target_mutation(
    context: ContextTypes.DEFAULT_TYPE,
    session: Any,
) -> str:
    settings: dict = context.bot_data["settings"]
    storage_root = resolve_project_path(settings["storage"]["root"])
    try:
        result = await run_sync(
            settings=settings,
            db_session=session,
            storage_root=storage_root,
        )
        return result.status
    except Exception:
        LOG.exception("Target mutation sync failed")
        return "sync_failed"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(
        update,
        "ScoutBot — monitoring assistant\n\n"
        "Commands:\n"
        "/start — intro\n"
        "/help — usage\n"
        "/add <url> — add target\n"
        "/projects — list projects\n"
        "/targets — list targets\n"
        "/pause <id> — pause target\n"
        "/resume <id> — resume target\n"
        "/delete <id> — delete target\n"
        "/check — run sync check",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(
        update,
        "Usage:\n\n"
        "/add https://example.com — add website for monitoring\n"
        "/projects — list monitored projects\n"
        "/targets — list recent targets\n"
        "/pause tgt_abc123 — pause monitoring\n"
        "/resume tgt_abc123 — resume monitoring\n"
        "/delete tgt_abc123 — delete target\n"
        "/check — trigger changedetection sync",
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _reply(update, "⛔ Admin only.")
        return

    args = context.args
    if not args:
        await _reply(update, "Usage: /add <url>")
        return

    url = args[0].strip()

    settings: dict = context.bot_data["settings"]
    workspace_name = settings["workspace"]["default_name"]
    discovery_cfg = settings["discovery"]
    allow_private = settings["discovery"]["allow_private_networks"]

    try:
        validate_url(url, allow_private_networks=allow_private)
        url = normalize_url(url)
    except ValueError as exc:
        await _reply(update, f"❌ Invalid URL: {exc}")
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        result = add_target(
            session=session,
            url=url,
            workspace_name=workspace_name,
            actor_telegram_id=str(user.id),
        )

        if discovery_cfg["enabled"]:
            from scoutbot_module.services.discovery import run_bounded_discovery_async

            storage_root = resolve_project_path(settings["storage"]["root"])

            disc_result = await run_bounded_discovery_async(
                session=session,
                target_id=result["target_id"],
                url=url,
                settings=settings,
                storage_root=str(storage_root),
            )
            result["links_found"] = disc_result.get("links_found", 0)
            result["children_created"] = disc_result.get("children_created", 0)

        storage_root = resolve_project_path(settings["storage"]["root"])

        sync_result = await run_sync(
            settings=settings,
            db_session=session,
            storage_root=storage_root,
        )
        result["sync_status"] = sync_result.status

        message = format_add_result(result)
        await _reply(
            update,
            message,
            reply_markup=build_target_actions_keyboard(result["target_id"]),
        )

    except Exception:
        LOG.exception("Error in /add")
        await _reply(update, "❌ Add failed. Check logs.")
    finally:
        session.close()
        engine.dispose()


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _reply(update, "⛔ Admin only.")
        return

    settings: dict = context.bot_data["settings"]
    workspace_name = settings["workspace"]["default_name"]

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        from scoutbot_module.services.targets import get_projects_list

        projects = get_projects_list(session, workspace_name)
        message = format_projects_list(projects)
        await _reply(update, message)
    finally:
        session.close()
        engine.dispose()


async def cmd_targets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _reply(update, "⛔ Admin only.")
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        from scoutbot_module.services.targets import get_targets_list

        targets = get_targets_list(session, limit=20)
        message = format_targets_list(targets)
        await _reply(update, message)
    finally:
        session.close()
        engine.dispose()


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _reply(update, "⛔ Admin only.")
        return

    args = context.args
    if not args:
        await _reply(update, "Usage: /pause <id>")
        return

    target_id = args[0].strip()
    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        from scoutbot_module.services.targets import pause_target

        result = pause_target(session, target_id, str(user.id))
        if result:
            sync_status = await _sync_after_target_mutation(context, session)
            await _reply(
                update,
                f"⏸ Paused: {result['title']} ({target_id})\nSync: {sync_status}",
            )
        else:
            await _reply(update, f"❌ Target not found: {target_id}")
    finally:
        session.close()
        engine.dispose()


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _reply(update, "⛔ Admin only.")
        return

    args = context.args
    if not args:
        await _reply(update, "Usage: /resume <id>")
        return

    target_id = args[0].strip()
    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        from scoutbot_module.services.targets import resume_target

        result = resume_target(session, target_id, str(user.id))
        if result:
            sync_status = await _sync_after_target_mutation(context, session)
            await _reply(
                update,
                f"▶ Resumed: {result['title']} ({target_id})\nSync: {sync_status}",
            )
        else:
            await _reply(update, f"❌ Target not found: {target_id}")
    finally:
        session.close()
        engine.dispose()


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _reply(update, "⛔ Admin only.")
        return

    args = context.args
    if not args:
        await _reply(update, "Usage: /delete <id>")
        return

    target_id = args[0].strip()
    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        from scoutbot_module.services.targets import delete_target

        result = delete_target(session, target_id, str(user.id))
        if result:
            sync_status = await _sync_after_target_mutation(context, session)
            await _reply(
                update,
                f"🗑 Deleted: {result['title']} ({target_id})\nSync: {sync_status}",
            )
        else:
            await _reply(update, f"❌ Target not found: {target_id}")
    finally:
        session.close()
        engine.dispose()


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _reply(update, "⛔ Admin only.")
        return

    settings: dict = context.bot_data["settings"]
    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)

    try:
        storage_root = resolve_project_path(settings["storage"]["root"])

        result = await run_sync(
            settings=settings,
            db_session=session,
            storage_root=storage_root,
        )

        await _reply(
            update,
            f"Sync: {result.status}\n"
            f"Created: {result.summary['created']}\n"
            f"Updated: {result.summary['updated']}\n"
            f"Failed: {result.summary['failed']}",
        )
    except Exception:
        LOG.exception("Error in /check")
        await _reply(update, "❌ Check failed. Check logs.")
    finally:
        session.close()
        engine.dispose()


async def handle_target_action_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None:
        return

    try:
        await query.answer()
    except Exception:
        LOG.warning("Failed to answer callback query")

    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    user = update.effective_user
    if user is None or user.id not in admin_ids:
        await _safe_callback_reply(update, "⛔ Admin only.")
        return

    data = query.data or ""
    parts = data.split(":", 2)
    if len(parts) != 3:
        await _safe_callback_reply(update, "❌ Invalid target action.")
        return

    _, action, target_id = parts
    if action == "noise":
        await _safe_callback_reply(
            update,
            "Noise marking will be available in Iteration 2.",
            reply_markup=build_target_actions_keyboard(target_id),
        )
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        if action == "pause":
            from scoutbot_module.services.targets import pause_target

            result = pause_target(session, target_id, str(user.id))
            if result is not None:
                sync_status = await _sync_after_target_mutation(context, session)
                text = f"⏸ Paused: {result['title']} ({target_id})\nSync: {sync_status}"
            else:
                text = f"❌ Target not found: {target_id}"
            reply_markup = (
                build_target_actions_keyboard(target_id) if result is not None else None
            )
        elif action == "resume":
            from scoutbot_module.services.targets import resume_target

            result = resume_target(session, target_id, str(user.id))
            if result is not None:
                sync_status = await _sync_after_target_mutation(context, session)
                text = (
                    f"▶ Resumed: {result['title']} ({target_id})\nSync: {sync_status}"
                )
            else:
                text = f"❌ Target not found: {target_id}"
            reply_markup = (
                build_target_actions_keyboard(target_id) if result is not None else None
            )
        elif action == "delete":
            from scoutbot_module.services.targets import delete_target

            result = delete_target(session, target_id, str(user.id))
            if result is not None:
                sync_status = await _sync_after_target_mutation(context, session)
                text = (
                    f"🗑 Deleted: {result['title']} ({target_id})\nSync: {sync_status}"
                )
            else:
                text = f"❌ Target not found: {target_id}"
            reply_markup = None
        else:
            await _safe_callback_reply(update, "❌ Unsupported target action.")
            return

        await _safe_callback_reply(update, text, reply_markup=reply_markup)
    except Exception:
        LOG.exception("Target action callback failed")
        await _safe_callback_reply(update, "❌ Target action failed.")
    finally:
        session.close()
        engine.dispose()


def create_bot_app(
    token: str,
    admin_ids: set[int],
    settings: dict,
    db_path: Any,
):
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler

    app = Application.builder().token(token).build()

    app.bot_data["admin_ids"] = admin_ids
    app.bot_data["settings"] = settings
    app.bot_data["db_path"] = db_path

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("targets", cmd_targets))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(
        CallbackQueryHandler(handle_target_action_callback, pattern=r"^target:")
    )

    return app
