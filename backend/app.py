"""WSGI and local entry point for the web backend."""
import os
from backend.map_predict import create_app
from backend.map_predict.api.assessment import legacy, _api_error
from backend.map_predict.config import ROOT

app = create_app(legacy_blueprint=legacy, legacy_error_handler=_api_error)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), debug=False)
