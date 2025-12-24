import json
import queue
import logging
import threading
import watchtower
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
        self.logger = logging.getLogger("TaskScheduler")
        self.logger.addHandler(watchtower.CloudWatchLogHandler(log_group='Fetcher', stream_name='fetcher'))

        with open("config.json", "r") as f:
            config = json.load(f)
        update_hour = config["dailyIncrementalUpdateHour"]
        update_minute = config["dailyIncrementalUpdateMinute"]
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            self.__incremental_update,
            trigger="cron",
            hour=update_hour,
            minute=update_minute
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
            self.instant_update_queue.put({
                "bubble_user_id": bubble_user_id,
                "type": "incremental"
            })

    def instant_update(self):
        bubble_user_id = None
        
        while True:
            try:
                update_info = self.instant_update_queue.get()
                bubble_user_id = update_info["bubble_user_id"]
                update_type = update_info["type"]
                self.logger.info(f"Processing new bubble user id: {bubble_user_id} with update type: {update_type}")
                reset_state = self.data.reset(bubble_user_id)
                if not reset_state:
                    self.logger.warning(f"Bubble ID: {bubble_user_id} invalid, skipping")
                    continue
                self.filter_instance.filter_messages(self.data, update_type)

            except Exception as e:
                self.logger.error(f"Error processing bubble user id {bubble_user_id}: {e}")
                continue