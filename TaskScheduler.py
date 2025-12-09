import queue
import logging
import threading
from Filters import Filter
from EmailLoader import Data
from NewUsrHandler import NewUsrHandler

class TaskScheduler:
    def __init__(self):
        self.instant_update_queue = queue.Queue()
        self.new_usr_listener = self.__start_new_usr_listener()
        self.data = Data()
        self.filter_instance = Filter()

    def __start_new_usr_listener(self):
        new_usr_handler = NewUsrHandler(self.instant_update_queue)
        new_usr_thread = threading.Thread(target=new_usr_handler.listen_new_usr)
        new_usr_thread.daemon = True
        new_usr_thread.start()
        return new_usr_thread

    def instant_update(self):
        while True:
            try:
                bubble_user_id = self.instant_update_queue.get()
                logging.info(f"Processing new bubble user id: {bubble_user_id}")
                self.data.reset(bubble_user_id)
                self.filter_instance.filter_messages(self.data)

            except queue.Empty:
                continue