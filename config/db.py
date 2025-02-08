from sqlalchemy.ext.asyncio import create_async_engine

# online_engine = create_async_engine(
#     "mysql+aiomysql://root:@localhost:3306", pool_size=16, max_overflow=0)


# auth_engine = create_async_engine(
#     "mysql+aiomysql://root:qgQGvM8FwI9fArc2ZqY8TkvbeynQPwY1@103.127.134.84:3306/event_commitee_kartjis", pool_size=16, max_overflow=0)

online_engine = create_async_engine(
    "mysql+aiomysql://root:qgQGvM8FwI9fArc2ZqY8TkvbeynQPwY1@103.127.134.84:3306", pool_size=16, max_overflow=0)
