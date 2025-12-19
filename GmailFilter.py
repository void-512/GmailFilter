import logging
import uvicorn
import threading
from TaskScheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def start_fastapi():
    uvicorn.run(
        "WebServer:app",
        host="0.0.0.0",
        port=1111,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    # Start FastAPI server in a background thread
    fastapi_thread = threading.Thread(target=start_fastapi, daemon=True)
    fastapi_thread.start()
    task_scheduler = TaskScheduler()
    task_scheduler.instant_update()