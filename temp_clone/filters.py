# Add a jinja2 filter for base64 encoding binary images
import base64
from flask import Flask

def register_b64(app: Flask):
    @app.template_filter('b64encode')
    def b64encode_filter(data):
        if not data:
            return ''
        return base64.b64encode(data).decode('ascii')
