"""Local TRACE desktop window with an application-owned server."""
import socket
import threading
import time
import urllib.request

import uvicorn
import webview


def main():
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config('backend.app:app', log_level='warning'))
    worker = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{port}'
    try:
        for attempt in range(100):
            try:
                urllib.request.urlopen(url + '/api/concept/state', timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError('TRACE server could not start.')
        webview.create_window('TRACE', url, width=1440, height=900, min_size=(1000, 700))
        webview.start(gui='edgechromium')
    finally:
        server.should_exit = True
        worker.join(timeout=5)
        listener.close()


if __name__ == '__main__':
    main()
