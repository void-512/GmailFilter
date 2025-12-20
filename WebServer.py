import json
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from NewUsrHandler import new_usr_queue
from UsrDeleter import delete_queue

security = HTTPBasic()
app = FastAPI()

with open("auth.json", "r") as f:
            auth = json.load(f)
VALID_USERNAME = auth["fetcher_endpoint"]["user"]
VALID_PASSWORD = auth["fetcher_endpoint"]["pwd"]

class UserData(BaseModel):
    bubble_user_id: str

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != VALID_USERNAME or credentials.password != VALID_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.post("/")
async def receive_id(data: UserData, user: str = Depends(authenticate)):
    logging.info(f"Received new id: {data.bubble_user_id}")

    new_usr_queue.put(data.bubble_user_id)
    return {"status": "ok"}

@app.post("/delete/")
async def delete_id(data: UserData, user: str = Depends(authenticate)):
    logging.info(f"Received delete request for id: {data.bubble_user_id}")

    delete_queue.put(data.bubble_user_id)
    return {"status": "deleted"}