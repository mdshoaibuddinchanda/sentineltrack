import json
from http.server import HTTPServer, BaseHTTPRequestHandler

MOCK_CATALOGUE = {
    'cameras': [
        {
            'camera_id': 'cam_01',
            'name': 'Junction 1 Northbound',
            'department': 'Traffic Operations',
            'latitude': 28.6139,
            'longitude': 77.2090,
            'codec': 'h264',
            'width': 1920,
            'height': 1080,
            'fps': 25.0,
            'live': True,
            'rtsp_url': 'rtsp://127.0.0.1:8554/live/cam_01',
            'stream': {
                'webrtc': 'http://127.0.0.1:8889/cam_01',
                'hls': 'http://127.0.0.1:8888/cam_01/index.m3u8'
            }
        },
        {
            'camera_id': 'cam_02',
            'name': 'Toll Plaza Lane 3',
            'department': 'Highway Authority',
            'latitude': 28.5355,
            'longitude': 77.3910,
            'codec': 'hevc',
            'width': 1280,
            'height': 720,
            'fps': 30.0,
            'live': True,
            'rtsp_url': 'rtsp://127.0.0.1:8554/live/cam_02',
        },
        {
            'camera_id': 'cam_03',
            'name': 'Expressway Exit 14',
            'department': 'Traffic Operations',
            'latitude': 28.4595,
            'longitude': 77.0266,
            'codec': 'h264',
            'width': 1920,
            'height': 1080,
            'fps': 25.0,
            'live': True,
            'rtsp_url': 'rtsp://127.0.0.1:8554/live/cam_03',
        }
    ]
}


class MockSentinelHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/ingest':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(MOCK_CATALOGUE, indent=2).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{\"error\": \"Not Found\"}')

    def log_message(self, format, *args):
        print(f'[MOCK SENTINEL] {self.address_string()} - {format % args}')


def run_server(port: int = 8000):
    server = HTTPServer(('0.0.0.0', port), MockSentinelHandler)
    print(f'[MOCK SENTINEL] Server running at http://localhost:{port}/api/ingest')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[MOCK SENTINEL] Stopping server...')
        server.server_close()


if __name__ == '__main__':
    run_server()
