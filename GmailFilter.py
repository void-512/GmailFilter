from EmailLoader import Data
from Filters import Filter
from TaskScheduler import TaskScheduler
import threading 
import uvicorn

def start_fastapi():
    uvicorn.run(
        "NewIDReceiver:app",
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