"""Local TRACE desktop window with an application-owned server."""
import socket
import threading
import sys

try:
    import uvicorn
    import webview
    from backend.app import app
except ImportError:
    if __name__ == '__main__':
        sys.exit(72)
    raise


def main():
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning'))
    worker = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{port}'
    try:
        webview.create_window('TRACE', url, width=1440, height=900, min_size=(1000, 700))
        webview.start(gui='edgechromium')
    finally:
        server.should_exit = True
        worker.join(timeout=5)
        listener.close()


if __name__ == '__main__':
    main()
