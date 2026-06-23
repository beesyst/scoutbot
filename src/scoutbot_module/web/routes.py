from __future__ import annotations

import hmac
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from scoutbot_module.db.session import create_db_engine, get_session
from scoutbot_module.web.schemas import WebhookEvent, WebhookResponse

LOG = logging.getLogger("scoutbot.web.routes")


def create_web_app(
    secret: str,
    settings: dict,
    db_path: str,
    body_bytes_max: int,
) -> FastAPI:
    app = FastAPI(title="ScoutBot Webhook")

    webhook_cfg = settings["webhook"]
    webhook_path = webhook_cfg["path"]

    @app.post(webhook_path)
    async def handle_webhook(
        request: Request,
        secret_param: str | None = Query(None, alias="secret"),
    ):
        if not secret:
            raise HTTPException(status_code=401, detail="Webhook secret not configured")

        provided_secret = secret_param or request.headers.get("x-webhook-secret", "")
        if not provided_secret:
            raise HTTPException(status_code=403, detail="Missing webhook secret")

        if not _constant_time_compare(provided_secret, secret):
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

        try:
            body = await _read_bounded_request_body(request, body_bytes_max)
            payload_raw = json.loads(body)
        except ValueError as exc:
            if str(exc) == "payload_too_large":
                raise HTTPException(
                    status_code=413, detail="Payload too large"
                ) from None
            raise HTTPException(
                status_code=400, detail="Invalid JSON payload"
            ) from None

        if not isinstance(payload_raw, dict):
            raise HTTPException(status_code=422, detail="Payload must be a JSON object")

        try:
            event = WebhookEvent(**payload_raw)
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid payload schema: {exc}"
            ) from exc

        cd_uuid = _extract_cd_uuid(event)
        if not cd_uuid:
            raise HTTPException(status_code=422, detail="Missing changedetection UUID")

        target_id, watch_id = _lookup_watch(db_path, cd_uuid)
        if not target_id or not watch_id:
            raise HTTPException(status_code=404, detail="Watch not found")

        from scoutbot_module.services.signals import process_webhook_event

        storage_root = settings["storage"]["root"]

        engine = create_db_engine(Path(db_path))
        session = get_session(engine)
        try:
            result = process_webhook_event(
                session=session,
                target_id=target_id,
                watch_id=watch_id,
                cd_uuid=cd_uuid,
                payload=payload_raw,
                storage_root=storage_root,
                settings=settings,
            )

            if not result.get("deduped"):
                await _dispatch_alert(
                    settings=settings,
                    signal=result,
                    target_id=target_id,
                    db_path=db_path,
                )

            return JSONResponse(
                content=WebhookResponse(
                    status="ok",
                    deduped=result.get("deduped", False),
                    signal_id=result.get("signal_id"),
                ).model_dump(),
                status_code=200,
            )
        finally:
            session.close()
            engine.dispose()

    return app


def _extract_cd_uuid(event: WebhookEvent) -> str | None:
    if event.uuid:
        return event.uuid
    if event.watch_uuid:
        return event.watch_uuid
    if event.changedetection_uuid:
        return event.changedetection_uuid
    if event.watch and isinstance(event.watch, dict):
        return event.watch.get("uuid")
    return None


def _lookup_watch(db_path: str, cd_uuid: str | None) -> tuple[str | None, str | None]:
    if not cd_uuid:
        return None, None

    from scoutbot_module.db.repo import find_watch_by_cd_uuid

    engine = create_db_engine(Path(db_path))
    session = get_session(engine)
    try:
        watch = find_watch_by_cd_uuid(session, cd_uuid)
        if watch:
            return watch.target_id, watch.watch_id
    finally:
        session.close()
        engine.dispose()
    return None, None


async def _dispatch_alert(
    settings: dict,
    signal: dict[str, Any],
    target_id: str | None,
    db_path: str,
) -> None:
    from scoutbot_module.services.notifications import send_telegram_alert_async

    target_info = None
    if target_id:
        from sqlmodel import select

        from scoutbot_module.db.models import Target

        engine = create_db_engine(Path(db_path))
        session = get_session(engine)
        try:
            tgt = session.exec(
                select(Target).where(Target.target_id == target_id)
            ).first()
            if tgt:
                from scoutbot_module.db.models import Project

                proj = session.exec(
                    select(Project).where(Project.project_id == tgt.project_id)
                ).first()
                target_info = {
                    "title": tgt.title,
                    "url": tgt.url,
                    "project_name": proj.name if proj else "Unknown",
                }
        finally:
            session.close()
            engine.dispose()

    await send_telegram_alert_async(
        settings=settings,
        signal=signal,
        target_info=target_info,
    )


def _constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


async def _read_bounded_request_body(request: Request, body_bytes_max: int) -> str:
    data = bytearray()
    async for chunk in request.stream():
        if not chunk:
            break
        if len(data) + len(chunk) > body_bytes_max:
            raise ValueError("payload_too_large")
        data.extend(chunk)
    return data.decode("utf-8", errors="replace")
