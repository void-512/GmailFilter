from fastapi import FastAPI
from pydantic import BaseModel
from NewUsrHandler import new_usr_queue
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

class UserData(BaseModel):
    bubble_user_id: str

@app.post("/")
async def receive_id(data: UserData):
    logging.info(f"Received new id: {data.dict()}")
    new_usr_queue.put(data.bubble_user_id)