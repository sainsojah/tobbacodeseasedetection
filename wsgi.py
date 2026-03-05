"""
WSGI entry point for production servers (Gunicorn on Render)
"""
from src.app import app 

if __name__ == "__main__":
    app.run()