import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, BigInteger, UniqueConstraint
import asyncio
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    platform = Column(String)
    customer_name = Column(String)
    summary = Column(Text)
    delivery = Column(Text)
    total = Column(Integer)
    paid = Column(Boolean, default=False)
    payment_method = Column(String)
    reference = Column(String, unique=True)
    deposit_address = Column(String)
    timestamp = Column(BigInteger)

class Conversation(Base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    platform = Column(String)
    history = Column(Text)
    __table_args__ = (UniqueConstraint('chat_id', 'platform', name='_chat_platform_uc'),)

class CircleWallet(Base):
    __tablename__ = 'circle_wallets'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True)
    wallet_id = Column(String, unique=True)
    chat_id = Column(String)
    platform = Column(String)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@asynccontextmanager
async def get_db_conn():
    async with AsyncSessionLocal() as session:
        yield session
