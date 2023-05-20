import json
from dataclasses import dataclass

@dataclass
class MinoConfig:
    telegram_api_key: str
    openai_api_key: str
    mino_api: str
    setu_db_name: str
    setu_db_user: str
    chatlog_db_user: str
    chatlog_db_password: str
    calendar_id: str
    awaiting_sending_calendar: int
    chatgpt_api_endpoint: str
    
    @staticmethod
    def new(config_path: str) -> 'MinoConfig':
        with open(config_path, 'r') as f:
            raw_conf = json.load(f)
        conf = MinoConfig(**raw_conf)
        conf.config_path = config_path
        return conf

    def dump(self) -> None:
        with open(self.config_path, 'w') as f:
            delattr(self, 'config_path')
            json.dump(self.__dict__, f)
