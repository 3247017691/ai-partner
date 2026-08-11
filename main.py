from fastapi import FastAPI

app = FastAPI()

# ————————常量—————————————
PRESET_FILE_PATH = "data/companion_presets.json"


@app.get("/api/presets", summary='取得所有AI伴侣预设数据，前端用于渲染选择下拉框')
async def presets():

    return {"message": "Hello World"}






if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000,)