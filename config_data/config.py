import os.path
from dataclasses import dataclass
import dotenv
import environs
from environs import Env

fields_id = {
    'manager_id_field': 1506979,
    'tg_id_field': 1104992,
    'status_id_field': 972634,
    'by_this_period_id_field': 1104934,
    'bonuses_id_field': 971580,
    'town_id_field': 972054,
    'full_price': 1105022,
    'pipeline_id': 1628622, #  7411865 - воронка тест 1628622 - воронка партнёры
    'tag_id': 606054,
    'status_id_order': 32809260, #  61586805 - статус переговоры 32809260 - статус новый заказ
    'status_id_kp': 39080307, # статус КП отправлено
    'chat_id': -4950490417,
    'catalog_id': 1682,
    'web_app_url': 'https://aleksslava.github.io/testwebapp.github.io/',
    'contacts_fields_id': {
        'tg_id_field': 1097296,
        'tg_username_field': 1097294
    },
    'lead_custom_fields': {
        'inn': 972566,
        'bik': 972568,
        'organization_adress': 1095240,
        'organization_account': 972570,
        'delivery_adress': 958756,
        'kard_pay': 1105338,
        'delivery_type': 971974
    }
}

# Класс с токеном бота телеграмм
@dataclass
class TgBot:
    token: str  #Токен для доступа к боту


# Класс с данными для подключения к API AMO
@dataclass
class AmoConfig:
    amocrm_subdomain: str
    amocrm_client_id: str
    amocrm_client_secret: str
    amocrm_redirect_url: str
    amocrm_access_token: str | None
    amocrm_refresh_token: str | None
    amocrm_secret_code: str
    path_to_env: str




# Класс с объектом TGBot
@dataclass
class Config:
    tg_bot: TgBot
    amo_config: AmoConfig


# Функция создания экземпляра класса config
def load_config(path: str | None = os.path.abspath('./.env')):
    env: Env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot(
            token=env("BOT_TOKEN")
        ),
        amo_config=AmoConfig(
            path_to_env=path,
            amocrm_subdomain=env("AMOCRM_SUBDOMAIN"),
            amocrm_client_id=env("AMOCRM_CLIENT_ID"),
            amocrm_client_secret=env("AMOCRM_CLIENT_SECRET"),
            amocrm_redirect_url=env("AMOCRM_REDIRECT_URL"),
            amocrm_access_token=env("AMOCRM_ACCESS_TOKEN"),
            amocrm_refresh_token=env("AMOCRM_REFRESH_TOKEN"),
            amocrm_secret_code=env("AMOCRM_SECRET")
        ))









