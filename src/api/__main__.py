"""Launch the FastAPI prototype on the loopback interface."""
import uvicorn

if __name__ == '__main__':
    uvicorn.run('src.api.main:app', host='127.0.0.1', port=8000)
