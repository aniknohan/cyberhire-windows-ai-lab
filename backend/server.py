import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, ensure_indexes  # noqa: E402
from lib.mode import WEB, public_url  # noqa: E402
from lib.seed import seed_all  # noqa: E402
from models.schemas import PublicConfig  # noqa: E402
from routers import auth, billing, content, interviews, practice, stats  # noqa: E402

if WEB and not os.environ.get("JWT_SECRET"):
    raise RuntimeError("JWT_SECRET must be set for the website (use a long random value).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot
    await seed_all()
    if WEB and os.environ.get("STRIPE_SECRET_KEY"):
        from lib.stripe_catalog import ensure_catalog

        async def _catalog():
            try:
                await asyncio.to_thread(ensure_catalog)
            except Exception as e:  # never block the site on billing setup; the log says what to fix
                logging.getLogger("stripe").error("Stripe catalog setup failed: %s", e)
        app.state.catalog_task = asyncio.create_task(_catalog())
    yield
    client.close()


app = FastAPI(lifespan=lifespan, title="CyberHire API", docs_url=None if WEB else "/docs", redoc_url=None, openapi_url=None if WEB else "/openapi.json")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "CyberHire API"}


@api_router.get("/config", response_model=PublicConfig)
async def public_config():
    return PublicConfig(mode="web" if WEB else "desktop", trial_days=billing.TRIAL_DAYS,
                        monthly_price_label=billing.PLANS["month"]["label"], yearly_price_label=billing.PLANS["year"]["label"],
                        google_login=bool(not WEB and os.environ.get("EMERGENT_GOOGLE_LOGIN")),
                        support_email=os.environ.get("SUPPORT_EMAIL", ""),
                        web_checkout=bool(os.environ.get("STRIPE_SECRET_KEY")),
                        play_store_url=os.environ.get("PLAY_STORE_URL", ""))


for module in (auth, interviews, content, practice, stats, billing):
    api_router.include_router(module.router)

def _cors_origins() -> list[str]:
    if os.environ.get("CORS_ORIGINS"):
        return [o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
    if WEB:  # the site itself + the Android app's bundled origin
        return [o for o in (public_url(), "https://localhost", "capacitor://localhost", "http://localhost") if o]
    return ["*"]


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    if WEB:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Token"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Include the router in the main app — keep last.
app.include_router(api_router)


# Desktop app: the built React UI is served from this same local server, so the frontend's
# relative /api calls and the session cookie work exactly as on the hosted site.
FRONTEND_DIR = Path(os.environ.get("SOC_FRONTEND_DIR") or (ROOT_DIR.parent / "frontend" / "dist")).resolve()
if FRONTEND_DIR.is_dir():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        f = (FRONTEND_DIR / full_path).resolve()
        if full_path and f.is_file() and FRONTEND_DIR in f.parents:
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if full_path.startswith("assets/") else {"Cache-Control": "no-cache"}
            return FileResponse(f, headers=headers)
        return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
