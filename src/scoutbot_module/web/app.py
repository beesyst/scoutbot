from __future__ import annotations

import logging
import os

from scoutbot_module.core.paths import resolve_project_path

LOG = logging.getLogger("scoutbot.web.app")


def run_webhook(settings: dict, argv: list[str]) -> int:
    del argv

    webhook_cfg = settings["webhook"]
    host = webhook_cfg["host"]
    port = webhook_cfg["port"]

    cd_cfg = settings["changedetection"]
    secret_env = cd_cfg["webhook_secret_env"]
    secret = os.environ.get(secret_env, "")

    if not secret:
        LOG.warning(
            "Webhook secret not found in env. "
            "All webhook requests will be rejected (401)."
        )

    storage_cfg = settings["storage"]
    db_path = str(resolve_project_path(storage_cfg["db_path"]))

    from scoutbot_module.web.routes import create_web_app

    app = create_web_app(
        secret=secret,
        settings=settings,
        db_path=db_path,
        body_bytes_max=webhook_cfg["body_bytes_max"],
    )

    import uvicorn

    LOG.info("Starting webhook server on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)
    return 0
