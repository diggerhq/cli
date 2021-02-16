#!/usr/bin/env python3

import random
import sys
import http.server as SimpleHTTPServer
import socketserver as SocketServer
from urllib.parse import urlparse
from urllib.parse import parse_qs
import logging
import sys


callback=None

class GetHandler(
        SimpleHTTPServer.SimpleHTTPRequestHandler
        ):

    def do_GET(self):
        # Extract query param
        query_components = parse_qs(urlparse(self.path).query)

        if 'redirect_uri' in query_components:
            redirect_uri = query_components["redirect_uri"][0]
        else:
            redirect_uri = 'https://app.digger.dev/'

        if 'token' in query_components:
            token = query_components["token"][0]
        else:
            print("WARNING: token not found, aborting")
            return

        # Sending an '200 OK' response
        self.send_response(301)

        self.send_header('Location', f'{redirect_uri}')
        
        # Whenever using 'send_header', you also have to call 'end_headers'
        self.end_headers()

        if callback is not None:
            callback(token)

        print("callback token completed successfully")
        sys.exit()

        return

class GetHandlerWithCallback(GetHandler):
    def __init__(self, callback):
        self.callback = callback

def start_server(port, callback_fn):
    global callback
    callback = callback_fn
    Handler = GetHandler
    print(f"server listening on port {port}")
    httpd = SocketServer.TCPServer(("", port), Handler)

    httpd.serve_forever()

