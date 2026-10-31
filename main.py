from orion_app.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run("orion_app.main:app", host="0.0.0.0", port=8000, reload=True)
