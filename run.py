import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compass import create_app

app = create_app()

if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "development")
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=debug)
