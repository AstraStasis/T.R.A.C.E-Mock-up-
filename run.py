"""One-command local launch after installing requirements."""
import os
import uvicorn

if __name__ == '__main__':
    uvicorn.run('backend.app:app', host=os.getenv('TRACE_HOST', '127.0.0.1'), port=int(os.getenv('TRACE_PORT', '8000')), ws='websockets')
