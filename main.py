import http.server
import socketserver
import os

PORT = int(os.environ.get("PORT", 3000))
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORKSPACE)

handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Dashboard running on port {PORT}")
    httpd.serve_forever()
