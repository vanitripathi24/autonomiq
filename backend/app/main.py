import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, inspect
from .db import SessionLocal, engine, Base
from . import models as m, seed, config
from .routes import router


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(m.Business.id).limit(1)):
            seed.seed(db)
    yield


app = FastAPI(title="AUTONOMIQ API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS or ["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
