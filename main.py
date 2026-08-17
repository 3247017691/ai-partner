import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.routers.chat import router as chat_router
from app.routers.presets import router as presets_router
from app.routers.sessions import router as sessions_router
from db import dispose_db, init_db


@asynccontextmanager
async def start_and_stop(app: FastAPI):
    try:
        logging.info('项目启动...')
        await init_db()
        yield
    finally:
        await dispose_db()
        logging.info('项目关闭...')


app = FastAPI(lifespan=start_and_stop)
app.include_router(chat_router)
app.include_router(presets_router)
app.include_router(sessions_router)



# -----------全局设置-----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
logging.getLogger("sqlalchemy.engine").propagate = False


@app.exception_handler(Exception)
def handle_exception(request: Request, e: Exception):
    logging.error(f"Exception on {request.method} {request.url}: {e}")
    return JSONResponse(content={"code": 500, "message": "系统正在维护,请重试或联系管理员"})




if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000, reload=False, access_log=False)
