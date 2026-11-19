from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hm_dianping_py.config.settings import settings
from hm_dianping_py.controller.dependencies import NotAuthenticated, refresh_login_user
from hm_dianping_py.controller.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.middleware("http")(refresh_login_user)
app.include_router(users_router)


@app.exception_handler(NotAuthenticated)
async def not_authenticated(_: Request, __: NotAuthenticated) -> Response:
    return Response(status_code=401)
