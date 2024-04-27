from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "mysql+aiomysql://root:toor@localhost:3306/atlantis", pool_size=16, max_overflow=0)
