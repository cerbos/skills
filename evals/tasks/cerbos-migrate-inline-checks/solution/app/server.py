"""Invoice service entry point: python /workspace/app/server.py"""

import os

from flask import Flask

import auth
import handlers


def create_app():
    app = Flask(__name__)
    auth.init_app(app)
    app.register_blueprint(handlers.bp)
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), threaded=True)
