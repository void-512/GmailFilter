import queue
import logging
import threading
from Filters import Filter
from EmailLoader import Data
from UsrDeleter import UsrDeleter
from NewUsrHandler import NewUsrHandler
from apscheduler.schedulers.background import BackgroundScheduler

class TaskScheduler:
    def __init__(self):
        self.instant_update_queue = queue.Queue()
        self.new_usr_listener = self.__start_new_usr_listener()
        self.data = Data()
        self.filter_instance = Filter()
        self.delete_usr_listener = self.__start_delete_usr_listener()

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self.__incremental_update,
            trigger="cron",
            hour=2,
            minute=30
        )
        scheduler.start()

    def __start_new_usr_listener(self):
        new_usr_handler = NewUsrHandler(self.instant_update_queue)
        new_usr_thread = threading.Thread(target=new_usr_handler.listen_new_usr)
        new_usr_thread.daemon = True
        new_usr_thread.start()
        return new_usr_thread

    def __start_delete_usr_listener(self):
        usr_deleter = UsrDeleter()
        delete_usr_thread = threading.Thread(target=usr_deleter.listen_delete_usr)
        delete_usr_thread.daemon = True
        delete_usr_thread.start()
        return delete_usr_thread

    def __incremental_update(self):
        bubble_user_ids = self.data.get_all_bubble_user_ids()
        for bubble_user_id in bubble_user_ids:
            self.instant_update_queue.put(bubble_user_id)

    def instant_update(self):
        bubble_user_id = None
        while True:
            try:
                bubble_user_id = self.instant_update_queue.get()
                logging.info(f"Processing new bubble user id: {bubble_user_id}")
                reset_state = self.data.reset(bubble_user_id)
                if not reset_state:
                    logging.warning(f"Bubble ID: {bubble_user_id} invalid, skipping")
                    continue
                self.filter_instance.filter_messages(self.data)

            except Exception as e:
                logging.error(f"Error processing bubble user id {bubble_user_id}: {e}")
                continue