from sqlalchemy.ext.asyncio import create_async_engine

online_engine = create_async_engine(
    "postgresql+asyncpg://postgres:ZC4I3DnWOsS9lv2dJeEozLm4GPzMSc8V@103.127.134.84:5432/db_kartjis_core", pool_size=16, max_overflow=0)
