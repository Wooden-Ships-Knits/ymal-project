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

from ymal import config_schema, config_store, registry, runner, settings

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
    # Compared as bytes: Starlette decodes headers as latin-1, and
    # compare_digest refuses a str containing non-ASCII, which would turn a
    # junk token into a 500 on an unauthenticated path instead of a 401.
    if not secrets.compare_digest(
        x_ymal_token.encode("utf-8", "surrogateescape"), API_TOKEN.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def _split_stamps(stored: dict) -> dict:
    """
    Separate the server-owned stamps from the config the console may send back.

    The stored document carries updated_at/updated_by, and config_schema
    rejects both on the way in. Returning them INSIDE `config` meant the
    console spread them into its next PUT, so every save after a page reload
    failed with 422. They travel as siblings instead, which makes the document
    the console holds exactly the document it is allowed to send.
    """
    config = dict(stored)
    return {
        "config": config,
        "updated_at": config.pop("updated_at", None),
        "updated_by": config.pop("updated_by", None),
    }


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/config")
def get_config() -> dict:
    try:
        result = config_store.read()
    except Exception as exc:
        # Deliberately NOT an empty config. "We cannot tell you what is placed"
        # is a different answer from "nothing is placed", and the console's red
        # banner exists to show the difference.
        raise HTTPException(
            status_code=502, detail=f"Could not read the configuration: {exc}"
        )

    return {**_split_stamps(result["config"]), "has_previous": result["has_previous"]}


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

    # Same split as GET: the restored document is a stored one, stamps and all.
    return {"ok": True, **_split_stamps(restored)}


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


@app.get("/api/run")
def get_run() -> dict:
    """Where the pipeline run has got to. Polled by the console while running."""
    return runner.status()


@app.post("/api/run")
def post_run(
    skip_copurchase: bool = Body(default=False, embed=True),
    x_ymal_token: str = Header(default=""),
) -> dict:
    """
    Start the pipeline by hand, instead of waiting for the schedule.

    Guarded like any other write: it ends by publishing to the live shop.

    Returns 409 when a run is already going. Two chains publishing at once
    would interleave their writes and leave the shop holding a mixture of two
    runs - the one outcome worth refusing outright.
    """
    require_token(x_ymal_token)

    result = runner.start(skip_copurchase=skip_copurchase)
    if not result["started"]:
        raise HTTPException(
            status_code=409,
            detail=f"A run is already in progress (started {result['started_at']}).",
        )
    return result
