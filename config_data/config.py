from dataclasses import dataclass
from environs import Env


# Класс с токеном бота телеграмм
@dataclass
class TgBot:
    token: str  #Токен для доступа к боту


# Класс с объектом TGBot
@dataclass
class Config:
    tg_bot: TgBot


# Функция создания экземпляра класса config
def load_config(path: str | None = None):
    env: Env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot(
            token=env("BOT_TOKEN")
        ))
