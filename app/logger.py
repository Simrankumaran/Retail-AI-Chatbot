import os
from pathlib import Path
import mlflow
from datetime import datetime

# Force MLflow to use a local file-based tracking URI and avoid bad env overrides
try:
    # Some environments set artifacts URI requiring HTTP tracking; unset for local file tracking
    os.environ.pop("MLFLOW_ARTIFACTS_URI", None)
    os.environ.pop("MLFLOW_ARTIFACT_URI", None)
    tracking_dir = Path("mlruns").resolve()
    mlflow.set_tracking_uri(tracking_dir.as_uri())  # e.g., file:///C:/.../mlruns
    # Optional: Log what tracking URI is used
    print("MLflow tracking URI:", mlflow.get_tracking_uri())
except Exception:
    # Non-fatal; logging will still attempt defaults
    pass

def log_interaction(query: str, response: str, tool_used: str = "auto"):
    try:
        mlflow.start_run(run_name=f"chat-{datetime.now().isoformat()}", nested=True)

        mlflow.log_param("query", query)
        mlflow.log_param("tool_used", tool_used)
        mlflow.log_text(response, "response.txt")
        mlflow.log_metric("response_length", len(response))

        mlflow.end_run()
    except Exception as e:
        print("⚠️ Logging failed:", e)
