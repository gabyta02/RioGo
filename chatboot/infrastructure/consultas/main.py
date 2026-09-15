from contextlib import asynccontextmanager

from fastapi import FastAPI

from infrastructure.websockett.websockett import websocket_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="RiobambaGo Chatboot", lifespan=lifespan)

app.include_router(websocket_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "chatboot"}
