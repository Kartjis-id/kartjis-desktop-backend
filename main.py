from fastapi import FastAPI
from routes.index import ticket

app = FastAPI()


app.include_router(ticket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
