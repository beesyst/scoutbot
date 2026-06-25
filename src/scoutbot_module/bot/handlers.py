from __future__ import annotations

import logging
from typing import Any

from sqlmodel import col
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


def _is_allowed(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    allowed_user_ids: set[int] = context.bot_data.get("allowed_user_ids", set())
    return user_id in allowed_user_ids


def _is_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    admin_ids: set[int] = context.bot_data.get("admin_ids", set())
    return user_id in admin_ids


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return
    if not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        from scoutbot_module.db.repo import get_telegram_subscriber_by_user_id

        sub = get_telegram_subscriber_by_user_id(session, str(user.id))
        if sub and sub.is_active:
            await _reply(
                update,
                "ScoutBot — monitoring assistant\n\n"
                "You are subscribed to alerts.\n"
                "/me — your status\n"
                "/unsubscribe — stop alerts\n"
                "/subscribe — re-subscribe\n"
                "/add <url> — add target\n"
                "/help — usage",
            )
        else:
            await _reply(
                update,
                "ScoutBot — monitoring assistant\n\n"
                "You are allowed but not subscribed.\n"
                "Use /subscribe to receive alerts.",
            )
    finally:
        session.close()
        engine.dispose()


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
        return

    await _reply(
        update,
        "Usage:\n\n"
        "/add https://example.com — add website for monitoring\n"
        "/projects — list monitored projects\n"
        "/targets — list recent targets\n"
        "/me — your status\n"
        "/subscribe — subscribe to alerts\n"
        "/unsubscribe — stop alerts\n"
        "/pause tgt_abc123 — pause monitoring\n"
        "/resume tgt_abc123 — resume monitoring\n"
        "/delete tgt_abc123 — delete target\n"
        "/check — trigger changedetection sync",
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
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
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
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
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
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
    user = update.effective_user
    if user is None or not _is_admin(context, user.id):
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
    user = update.effective_user
    if user is None or not _is_admin(context, user.id):
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
    user = update.effective_user
    if user is None or not _is_admin(context, user.id):
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
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
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


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        from scoutbot_module.db.repo import (
            upsert_telegram_subscriber,
            write_audit_log,
        )

        chat = update.effective_chat
        chat_id = str(chat.id) if chat else str(user.id)

        role = "admin" if _is_admin(context, user.id) else "operator"
        sub = upsert_telegram_subscriber(
            session=session,
            telegram_user_id=str(user.id),
            chat_id=chat_id,
            role=role,
            username=user.username,
            first_name=user.first_name,
        )
        write_audit_log(
            session,
            action="subscribe",
            actor_telegram_id=str(user.id),
            entity_type="telegram_subscriber",
            entity_id=sub.subscriber_id,
            payload={"chat_id": chat_id, "role": role},
        )
        await _reply(update, "✅ Subscribed to ScoutBot alerts.")
    finally:
        session.close()
        engine.dispose()


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        from scoutbot_module.db.repo import (
            deactivate_telegram_subscriber,
            write_audit_log,
        )

        sub = deactivate_telegram_subscriber(session, str(user.id))
        if sub:
            write_audit_log(
                session,
                action="unsubscribe",
                actor_telegram_id=str(user.id),
                entity_type="telegram_subscriber",
                entity_id=sub.subscriber_id,
            )
        await _reply(update, "✅ You have been unsubscribed from ScoutBot alerts.")
    finally:
        session.close()
        engine.dispose()


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _reply(update, "⛔ Access denied.")
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        from scoutbot_module.db.repo import get_telegram_subscriber_by_user_id

        sub = get_telegram_subscriber_by_user_id(session, str(user.id))
        is_subscribed = sub is not None and sub.is_active
        role = "admin" if _is_admin(context, user.id) else "operator"
        chat = update.effective_chat
        chat_id = str(chat.id) if chat else "unknown"

        lines = [
            "Your ScoutBot status",
            "",
            f"User ID: {user.id}",
            f"Chat ID: {chat_id}",
            f"Allowed: {'yes' if _is_allowed(context, user.id) else 'no'}",
            f"Role: {role}",
            f"Subscribed: {'yes' if is_subscribed else 'no'}",
        ]
        await _reply(update, "\n".join(lines))
    finally:
        session.close()
        engine.dispose()


async def cmd_subscribers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or not _is_admin(context, user.id):
        await _reply(update, "⛔ Admin only.")
        return

    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        from scoutbot_module.db.repo import list_telegram_subscribers

        subscribers = list_telegram_subscribers(session)
        if not subscribers:
            await _reply(update, "No subscribers.")
            return

        lines = ["Subscribers:"]
        for sub in subscribers:
            status = "🟢" if sub.is_active else "🔴"
            name = sub.first_name or sub.username or sub.telegram_user_id
            lines.append(f"{status} {name} [{sub.role}] — {sub.telegram_user_id}")
        await _reply(update, "\n".join(lines))
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

    user = update.effective_user
    if user is None or not _is_admin(context, user.id):
        await _safe_callback_reply(update, "⛔ Admin only.")
        return

    data = query.data or ""
    parts = data.split(":", 2)
    if len(parts) != 3:
        await _safe_callback_reply(update, "❌ Invalid target action.")
        return

    _, action, target_id = parts
    if action == "noise":
        await _handle_mark_noise(update, context, target_id)
        return

    from scoutbot_module.services.targets import (
        delete_target,
        pause_target,
        resume_target,
    )

    target_actions = {
        "pause": (pause_target, "⏸"),
        "resume": (resume_target, "▶"),
        "delete": (delete_target, "🗑"),
    }

    if action not in target_actions:
        await _safe_callback_reply(update, "❌ Unknown action.")
        return

    fn, emoji = target_actions[action]
    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        result = fn(session, target_id, str(user.id))
        if result:
            sync_status = await _sync_after_target_mutation(context, session)
            await _safe_callback_reply(
                update,
                f"{emoji} {result['title']} ({target_id})\nSync: {sync_status}",
            )
        else:
            await _safe_callback_reply(update, f"❌ Target not found: {target_id}")
    finally:
        session.close()
        engine.dispose()


async def handle_signal_action_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None:
        return

    try:
        await query.answer()
    except Exception:
        LOG.warning("Failed to answer callback query")

    user = update.effective_user
    if user is None or not _is_allowed(context, user.id):
        await _safe_callback_reply(update, "⛔ Access denied.")
        return

    data = query.data or ""
    parts = data.split(":", 2)
    if len(parts) != 3:
        await _safe_callback_reply(update, "❌ Invalid signal action.")
        return

    _, action, signal_id = parts
    if action != "noise":
        await _safe_callback_reply(update, "❌ Unknown action.")
        return

    await _handle_mark_signal_noise(update, context, signal_id)


async def _handle_mark_noise(
    update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: str
) -> None:
    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        from datetime import UTC, datetime

        from sqlmodel import select

        from scoutbot_module.core.paths import resolve_project_path
        from scoutbot_module.db.models import Signal, Target
        from scoutbot_module.db.repo import write_audit_log

        user = update.effective_user

        stmt = (
            select(Signal)
            .where(Signal.target_id == target_id)
            .order_by(col(Signal.detected_at).desc())
        )
        signal = session.exec(stmt).first()

        tgt = session.exec(select(Target).where(Target.target_id == target_id)).first()

        _mark_signal_noise(session, signal, tgt)

        if signal:
            write_audit_log(
                session,
                action="mark_as_noise",
                actor_telegram_id=str(user.id) if user else None,
                entity_type="signal",
                entity_id=signal.signal_id,
                payload={"target_id": target_id},
            )

        settings: dict = context.bot_data["settings"]
        storage_root = resolve_project_path(settings["storage"]["root"])
        run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        noise_path = storage_root / "runs" / run_id / "noise_update.json"
        noise_path.parent.mkdir(parents=True, exist_ok=True)
        with noise_path.open("w", encoding="utf-8") as f:
            import json

            json.dump(
                {
                    "target_id": target_id,
                    "signal_id": signal.signal_id if signal else None,
                    "action": "mark_as_noise",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        await _safe_callback_reply(
            update, f"🔇 Marked as noise: {tgt.title if tgt else target_id}"
        )
    except Exception:
        LOG.exception("Error marking as noise")
        await _safe_callback_reply(update, "❌ Failed to mark as noise.")
    finally:
        session.close()
        engine.dispose()


async def _handle_mark_signal_noise(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    signal_id: str,
) -> None:
    db_path = context.bot_data["db_path"]
    engine = create_db_engine(db_path)
    session = get_session(engine)
    try:
        import json
        from datetime import UTC, datetime

        from sqlmodel import select

        from scoutbot_module.core.paths import resolve_project_path
        from scoutbot_module.db.models import Signal, Target
        from scoutbot_module.db.repo import write_audit_log

        user = update.effective_user
        signal = session.exec(
            select(Signal).where(Signal.signal_id == signal_id)
        ).first()
        if signal is None:
            await _safe_callback_reply(update, f"❌ Signal not found: {signal_id}")
            return

        tgt = None
        if signal.target_id:
            tgt = session.exec(
                select(Target).where(Target.target_id == signal.target_id)
            ).first()

        _mark_signal_noise(session, signal, tgt)

        write_audit_log(
            session,
            action="mark_as_noise",
            actor_telegram_id=str(user.id) if user else None,
            entity_type="signal",
            entity_id=signal.signal_id,
            payload={"target_id": signal.target_id},
        )

        settings: dict = context.bot_data["settings"]
        storage_root = resolve_project_path(settings["storage"]["root"])
        run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        noise_path = storage_root / "runs" / run_id / "noise_update.json"
        noise_path.parent.mkdir(parents=True, exist_ok=True)
        with noise_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "target_id": signal.target_id,
                    "signal_id": signal.signal_id,
                    "action": "mark_as_noise",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        await _safe_callback_reply(
            update,
            f"🔇 Marked as noise: {signal.title or signal.signal_id}",
        )
    except Exception:
        LOG.exception("Error marking signal as noise")
        await _safe_callback_reply(update, "❌ Failed to mark as noise.")
    finally:
        session.close()
        engine.dispose()


def _mark_signal_noise(session: Any, signal: Any, target: Any) -> None:
    import json

    if signal:
        signal.category = "noise"
        signal.priority = "low"
        session.add(signal)

    if target:
        existing: list[str] = []
        if target.ignore_text_json:
            try:
                existing = json.loads(target.ignore_text_json)
                if not isinstance(existing, list):
                    existing = []
            except json.JSONDecodeError, TypeError:
                existing = []

        ignore_phrase = f"[noise:{signal.signal_id if signal else 'manual'}]"
        if ignore_phrase not in existing:
            existing.append(ignore_phrase)
            target.ignore_text_json = json.dumps(existing, ensure_ascii=False)
            session.add(target)

    session.commit()


def create_bot_app(
    token: str,
    admin_ids: set[int],
    allowed_user_ids: set[int],
    settings: dict,
    db_path: Any,
):
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler

    app = Application.builder().token(token).build()

    app.bot_data["admin_ids"] = admin_ids
    app.bot_data["allowed_user_ids"] = allowed_user_ids
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
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("subscribers", cmd_subscribers))
    app.add_handler(
        CallbackQueryHandler(handle_signal_action_callback, pattern=r"^signal:")
    )
    app.add_handler(
        CallbackQueryHandler(handle_target_action_callback, pattern=r"^target:")
    )

    return app
