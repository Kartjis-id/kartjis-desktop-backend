from fastapi import FastAPI
from routes.index import ticket

app = FastAPI()


app.include_router(ticket)
