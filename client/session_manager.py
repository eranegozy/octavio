from abc import ABC, abstractmethod
import logging
import string
import random
import datetime

logger = logging.getLogger(__name__)

class SessionManager(ABC):

    def get_session_id(self):
        return self.session_id

    @abstractmethod
    def handle_recording_activity(self):
        pass

    @abstractmethod
    def handle_button_pressed(self):
        pass

class ContinuousSessionManager(SessionManager):
    def __init__(self):
        self.session_id = None
        self.privacy_last_requested = None
        self.last_recording_activity = None

    def get_session_id(self):
        self.update_state()
        return super().get_session_id()

    def update_state(self):
        now = datetime.datetime.now()
        if self.privacy_last_requested and now - self.privacy_last_requested > datetime.timedelta(minutes=1): #TODO: config variable
            self.privacy_last_requested = None
        
        if self.last_recording_activity and now - self.last_recording_activity > datetime.timedelta(minutes=0.01): #TODO: config variable
            self.session_id = None
            self.last_recording_activity = None

    def handle_recording_activity(self):
        self.update_state()

        now = datetime.datetime.now()

        if self.privacy_last_requested: # with state updated, is not None only if privacy is still ongoing
            return
        
        if self.session_id is None:
            new_session_id = generate_id()
            print(new_session_id)
            logger.info(f"Recording activity detected. Creating new session with ID {new_session_id}")
            self.session_id = new_session_id
        self.last_recording_activity = now

    def handle_button_pressed(self):
        self.update_state()
        now = datetime.datetime.now()

        self.privacy_last_requested = now
        self.session_id = None
        self.last_recording_activity = None


# TODO: figure out whether to copy here or use the one in root utils.py
def generate_id():
    """Generates a random 10-character alphanumeric ID.

    Returns:
        str: A lowercase alphanumeric string of length 10.
    """
    id_options = string.ascii_lowercase + string.digits
    return ''.join(random.choices(population=id_options, k=10))

def get_session_manager():
    return ContinuousSessionManager()