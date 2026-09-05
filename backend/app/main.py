"""
The console's API.

Thin on purpose: it parses requests, calls into ymal/, and formats responses.
Every rule lives in ymal/config_schema.py, every Shopify call in
ymal/config_store.py. Nothing here decides anything.

Run:  cd backend && uvicorn app.main:app --reload
"""

import os
import secrets

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from ymal import config_schema, config_store, registry, settings

load_dotenv(settings.REPO_ROOT / ".env", override=True)

API_TOKEN = os.getenv("YMAL_API_TOKEN", "")

# Refuse to start rather than run open. A service that fails to start is a
# visible problem; a service quietly serving writes without auth is not.
# Follows fetch_products, which refuses to run when no location matches the
# Bali pattern rather than silently classifying the catalog as fixed stock.
if not API_TOKEN:
    raise RuntimeError(
        "YMAL_API_TOKEN is not set. Add it to .env at the repository root — "
        "the API will not start without it, because writes reach the live shop."
    )

app = FastAPI(title="YMAL Console API")


def require_token(x_ymal_token: str) -> None:
    """
    Guard every write.

    compare_digest rather than == so a wrong token takes the same time to
    reject regardless of how much of it was right.
    """
    if not secrets.compare_digest(x_ymal_token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/config")
def get_config() -> dict:
    try:
        return config_store.read()
    except Exception as exc:
        # Deliberately NOT an empty config. "We cannot tell you what is placed"
        # is a different answer from "nothing is placed", and the console's red
        # banner exists to show the difference.
        raise HTTPException(
            status_code=502, detail=f"Could not read the configuration: {exc}"
        )


@app.put("/api/config")
def put_config(
    config: dict = Body(...),
    x_ymal_token: str = Header(default=""),
) -> JSONResponse:
    require_token(x_ymal_token)

    errors = config_schema.validate(config)
    if errors:
        return JSONResponse(status_code=422, content={"errors": errors})

    try:
        stored = config_store.write(config, updated_by="web-team")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not save: {exc}")

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "version": stored["version"],
            "updated_at": stored["updated_at"],
        },
    )


@app.post("/api/config/undo")
def post_undo(x_ymal_token: str = Header(default="")) -> dict:
    require_token(x_ymal_token)

    try:
        restored = config_store.undo()
    except config_store.NoPreviousConfig as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not undo: {exc}")

    return {"ok": True, "config": restored}


@app.get("/api/blocks")
def get_blocks() -> list[dict]:
    try:
        published = config_store.published_block_ids()
    except Exception:
        # A block list we cannot check is reported as unpublished. The console
        # then warns about a block that may in fact be fine, which is the safe
        # direction to be wrong in.
        published = set()

    return [
        {
            "id": block["id"],
            "label": block["label"],
            "description": block["description"],
            "requires_anchor": block["requires_anchor"],
            "supported_page_templates": registry.supported_page_templates(block["id"]),
            "default_heading": block["default_heading"],
            "default_slots": block["default_slots"],
            "list_published": block["id"] in published,
        }
        for block in registry.BLOCKS
    ]


@app.get("/api/page-templates")
def get_page_templates() -> list[dict]:
    return [
        {"id": t["id"], "label": t["label"], "live": t["live"], "anchor": t["anchor"]}
        for t in registry.PAGE_TEMPLATES
    ]
