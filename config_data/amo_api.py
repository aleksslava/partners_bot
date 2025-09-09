import pprint

import dotenv
import jwt
import requests
from datetime import datetime
import logging

from pydantic import json
from requests.exceptions import JSONDecodeError
from config_data.config import load_config

logger = logging.getLogger(__name__)


class Contact:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.custom_fields_values = kwargs.get('custom_fields_values')
        self.phone_list = self._get_contact_data_list(field_name='Телефон')
        self.mail_list = self._get_contact_data_list(field_name='Email')

    def _get_contact_data_list(self, field_name) -> list:
        data = []
        for field in self.custom_fields_values:
            if field.get('field_name') == field_name:
                for arg in field.get('values'):
                    data.append(arg.get('value'))

        return data

    def __str__(self):
        contact_message = f'\n{self.name}\n'

        for number in self.phone_list:
            value = f'📞 {number}\n'
            contact_message = contact_message + value

        for email in self.mail_list:
            value = f'📧 {email}\n'
            contact_message = contact_message + value

        return contact_message


class Customer:
    # Список доступных статусов партнёра
    partner_status_dct: dict[str, list] = {
        'Отсутствует': ['скидка 0%', 0],
        'Старт': ['скидка 15%', 0],
        'База': ['скидка 20%', 100000],
        'Бронза': ['скидка 25%', 200000],
        'Серебро': ['скидка 30%', 500000],
        'Золото': ['скидка 35%',],
        'Платина': ['скидка 40%',],
        'Бизнес': ['скидка 40%',],
        'Эксклюзив': ['Индивидуальные условия',]
    }

    partner_status_list: list = [
        'Отсутствует', 'Старт', 'База', 'Бронза', 'Серебро', 'Золото', 'Платина', 'Бизнес', 'Эксклюзив'
    ]

    def __init__(self, fields_id: dict[str, int]):
        self.fields_id = fields_id

    def __call__(self, customer_dct: dict):
        self.id = customer_dct.get('id')
        self.name = customer_dct['name']
        self.itv = customer_dct.get('itv')  # Сумма покупок партнёра
        self.custom_fields = customer_dct['custom_fields_values']
        self.manager = customer_dct.get('manager').get('name')
        self.status = self.get_status(self.custom_fields)
        self.bye_in_this_period = self.bye_this_period(self.custom_fields)
        self.bonuses = self.get_bonuses(self.custom_fields)
        self.town = self.get_town(self.custom_fields)
        self.next_status = self.get_next_status(self.status)
        self.tg_id: bool = self.get_customer_tg_id(self.custom_fields)
        self.full_price = self.get_customer_full_price(self.custom_fields)


        return self

    def get_customer_full_price(self, values: list):
        if values is None:
            return 0
        full_price_list = [res for res in values if res['field_id'] == self.fields_id.get('full_price')]
        if not full_price_list:
            return 0
        full_price = full_price_list[0].get('values')[0].get('value')
        full_price = f'{int(full_price):,}'.replace(',', ' ')
        return full_price

    def get_customer_tg_id(self, values: list):
        if values is None:  # Если нет записанного id_tg у партнёра, то True иначе False
            return True

        tg_id = [res for res in values if res['field_id'] == self.fields_id.get('tg_id_field')]
        if tg_id:
            return False
        return True


    def get_status(self, values: list):
        if values is None:
            return f'Отсутствует, {self.partner_status_dct.get("Отсутствует")[0]}'
        status = [res for res in values if res['field_id'] == self.fields_id.get('status_id_field')]
        if not status:
            return f'Отсутствует, {self.partner_status_dct.get("Отсутствует")[0]}'
        status_value: str = status[0].get('values')[0].get('value').split()[0]
        return f'{status_value}, {self.partner_status_dct.get(status_value)[0]}'

    def bye_this_period(self, values: list):
        if values is None:
            return 0
        summ = [res for res in values if res['field_id'] == self.fields_id.get('by_this_period_id_field')]
        if not summ:
            return 0
        summ_value = summ[0].get('values')[0].get('value')
        return summ_value

    def get_bonuses(self, values: list):
        if values is None:
            return 0
        bonuses = [res for res in values if res['field_id'] == self.fields_id.get('bonuses_id_field')]
        if not bonuses:
            return 0
        bonuses_value = bonuses[0].get('values')[0].get('value')
        bonuses_value = f'{int(bonuses_value):,}'.replace(',', ' ')
        return bonuses_value

    def get_town(self, values: list):
        if values is None:
            return 'Отсутствует'
        town = [res for res in values if res['field_id'] == self.fields_id.get('town_id_field')]
        if not town:
            return 'Отсутствует'
        town_value = town[0].get('values')[0].get('value')
        return town_value

    def get_next_status(self, partner_status):
        ind = 1
        for index, status in enumerate(self.partner_status_list):
            if status in partner_status.split()[0]:
                ind = index

        if len(self.partner_status_list) == ind + 1:
            next_status = self.partner_status_list[ind]
        else:
            next_status = self.partner_status_list[ind+1]

        return f'{next_status}, {self.partner_status_dct.get(next_status)[0]}'


class AmoCRMWrapper:
    def __init__(self,
                 path: str,
                 amocrm_subdomain: str,
                 amocrm_client_id: str,
                 amocrm_client_secret: str,
                 amocrm_redirect_url: str,
                 amocrm_access_token: str | None,
                 amocrm_refresh_token: str | None,
                 amocrm_secret_code: str
                 ):
        self.path_to_env = path
        self.amocrm_subdomain = amocrm_subdomain
        self.amocrm_client_id = amocrm_client_id
        self.amocrm_client_secret = amocrm_client_secret
        self.amocrm_redirect_url = amocrm_redirect_url
        self.amocrm_access_token = amocrm_access_token
        self.amocrm_refresh_token = amocrm_refresh_token
        self.amocrm_secret_code = amocrm_secret_code


    @staticmethod
    def _is_expire(token: str):
        token_data = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.utcfromtimestamp(token_data["exp"])
        now = datetime.utcnow()

        return now >= exp

    def _save_tokens(self, access_token: str, refresh_token: str):
        dotenv.set_key(self.path_to_env, "AMOCRM_ACCESS_TOKEN", access_token)
        dotenv.set_key(self.path_to_env, "AMOCRM_REFRESH_TOKEN", refresh_token)
        self.amocrm_access_token = access_token
        self.amocrm_refresh_token = refresh_token

    def _get_access_token(self):
        return self.amocrm_access_token

    def _get_new_tokens(self):
        data = {
            "client_id": self.amocrm_client_id,
            "client_secret": self.amocrm_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.amocrm_refresh_token,
            "redirect_uri": self.amocrm_redirect_url
        }
        response = requests.post("https://{}.amocrm.ru/oauth2/access_token".format(self.amocrm_subdomain),
                                 json=data).json()
        try:
            access_token = response["access_token"]
            refresh_token = response["refresh_token"]
        except KeyError as error:
            logger.error("Ошибка обновления токенов")
            return False

        self._save_tokens(access_token, refresh_token)

    def init_oauth2(self):
        data = {
            "client_id": self.amocrm_client_id,
            "client_secret": self.amocrm_client_secret,
            "grant_type": "authorization_code",
            "code": self.amocrm_secret_code,
            "redirect_uri": self.amocrm_redirect_url
        }

        response = requests.post("https://{}.amocrm.ru/oauth2/access_token".format(self.amocrm_subdomain),
                                 json=data).json()

        access_token = response["access_token"]
        refresh_token = response["refresh_token"]

        self._save_tokens(access_token, refresh_token)

    def _base_request(self, **kwargs) -> json:
        if self._is_expire(self._get_access_token()):
            self._get_new_tokens()

        access_token = "Bearer " + self._get_access_token()

        headers = {"Authorization": access_token}
        req_type = kwargs.get("type")
        response = ""
        if req_type == "get":
            response = requests.get("https://{}.amocrm.ru{}".format(
                self.amocrm_subdomain, kwargs.get("endpoint")), headers=headers)

        elif req_type == "get_param":
            url = "https://{}.amocrm.ru{}?{}".format(
                self.amocrm_subdomain,
                kwargs.get("endpoint"), kwargs.get("parameters"))
            response = requests.get(str(url), headers=headers)

        elif req_type == "post":
            response = requests.post("https://{}.amocrm.ru{}".format(
                self.amocrm_subdomain,
                kwargs.get("endpoint")), headers=headers, json=kwargs.get("data"))

        elif req_type == 'patch':
            response = requests.patch("https://{}.amocrm.ru{}".format(
                self.amocrm_subdomain,
                kwargs.get("endpoint")), headers=headers, json=kwargs.get("data"))
        return response

    def get_contact_by_phone(self, phone_number, with_customer=False) -> tuple:
        phone_number = str(phone_number)[2:]
        url = '/api/v4/contacts'
        if with_customer:
            query = str(f'query={phone_number}&with=customers')
        else:
            query = str(f'query={phone_number}')
        contact = self._base_request(endpoint=url, type="get_param", parameters=query)
        if contact.status_code == 200:
            contacts_list = contact.json()['_embedded']['contacts']
            if len(contacts_list) > 1:  # Проверка на дубли номера телефона в контактах
                return False, ('Найдено более одного контакта с номером телефона\n'
                               'Обратитесь к менеджеру отдела продаж!')
            else:
                return True, contacts_list[0]
        elif contact.status_code == 204:
            return False, 'Контакт не найден'
        else:
            logger.error('Нет авторизации в AMO_API')
            return False, 'Произошла ошибка на сервере!'

    def get_customer_by_phone(self, phone_number) -> tuple:
        contact = self.get_contact_by_phone(phone_number, with_customer=True)
        if contact[0]:  # Проверка, что ответ от сервера получен
            contact = contact[1]
            customer_list = contact['_embedded']['customers']
            if len(customer_list) > 1:
                return False, 'К номеру телефона привязано более одного партнёра'
            elif not customer_list:
                return False, 'К номеру телефона не привязано ни одного партнёра'
            customer_id = customer_list[0]['id']
            url = f'/api/v4/customers/{customer_id}'
            customer = self._base_request(endpoint=url, type='get').json()

            return True, customer
        else:
            return contact

    def get_customer_by_id(self, customer_id, with_contacts=False) -> tuple:
        url = f'/api/v4/customers/{customer_id}'
        try:
            if with_contacts:
                query = str(f'with=contacts')
                customer = self._base_request(endpoint=url, type='get_param', parameters=query)
            else:
                customer = self._base_request(endpoint=url, type='get')
        except Exception as error:
            return False, "Произошла ошибка на сервере"
        if customer.status_code == 200:
            return True, customer.json()
        elif customer.status_code == 204:
            return False, 'Партнёр не найден!'
        else:
            logger.error('Нет авторизации в AMO_API')
            return False, 'Произошла ошибка на сервере!'

    def get_customer_by_tg_id(self, tg_id: int) -> dict:  # Нужно убрать все id полей амо в конфиг
        url = '/api/v4/customers'
        field_id = '1104992'
        query = str(f'filter[custom_fields_values][{field_id}][]={tg_id}')
        response = self._base_request(endpoint=url, type='get_param', parameters=query)

        if response.status_code == 200:
            customer_list = response.json()['_embedded']['customers']
            if len(customer_list) > 1:
                return {'status_code': False,
                        'tg_id_in_db': False,
                        'response': 'Найдено более одного номера tg_id в базе данных\n'
                                    'Обратитесь к Вашему менеджеру'
                        }
            return {'status_code': True,
                    'tg_id_in_db': True,
                    'response': customer_list[0]
                    }

        elif response.status_code == 204:
            return {'status_code': True,
                    'tg_id_in_db': False,
                    'response': 'Телеграмм id не найден в базе данных'
                    }

        else:
            return {'status_code': False,
                    'tg_id_in_db': False,
                    'response': 'Произошла ошибка на сервере'
                    }

    def put_tg_id_to_customer(self, id_customer, tg_id):
        url = f'/api/v4/customers/{id_customer}'
        data = {"custom_fields_values": [
            {"field_id": 1104992,
             "values": [
                 {"value": f"{tg_id}"},
                 ]
             }]}
        response = self._base_request(type='patch', endpoint=url, data=data)
        logger.info(f'Запись ID_telegram: {tg_id} в карту партнёра: {id_customer}\n'
                    f'Статус операции: {response.status_code}')


    def send_lead_to_amo(self, pipeline_id: int, status_id: int, tag_id: int, contact_id: int,
                         price: int):
        url = f'/api/v4/leads'
        data = [{
            'name': 'Заказ с чат_бота',
            'pipeline_id': pipeline_id,
            'created_by': 0,
            'status_id': status_id,
            'price': price,
            'responsible_user_id': 453498,
            '_embedded': {
                'tags': [
                    {
                        'id': tag_id
                    }
                ],
                'contacts': [
                    {
                        'id': contact_id
                    }
                ]
            }

        },]
        response = self._base_request(type='post', endpoint=url, data=data)
        return response.json()

    def add_new_note_to_lead(self, lead_id, text):
        url = f'/api/v4/leads/{lead_id}/notes'
        data = [
            {
                'note_type': 'common',
                'params': {
                    'text': text
                }
            }
        ]
        response = self._base_request(type='post', endpoint=url, data=data)
        return response.json()


    def get_contact_by_id(self, contact_id) -> dict:
        url = f'/api/v4/contacts/{contact_id}'
        response = self._base_request(type='get', endpoint=url)

        return response.json()

    def get_responsible_user_by_id(self, manager_id: int):
        url = f'/api/v4/users/{manager_id}'

        responsible_manager = self._base_request(endpoint=url, type='get')
        if responsible_manager.status_code == 200:
            return responsible_manager.json()
        else:
            raise JSONDecodeError




    @staticmethod
    def get_customer_params(customer_dct: dict[str, str], fields_id: dict) -> Customer:
        customer = Customer(fields_id)
        customer = customer(customer_dct)
        return customer


if __name__ == '__main__':
    from config_data.config import load_config, Config
    config: Config = load_config()

    amo_api = AmoCRMWrapper(
        path=config.amo_config.path_to_env,
        amocrm_subdomain=config.amo_config.amocrm_subdomain,
        amocrm_client_id=config.amo_config.amocrm_client_id,
        amocrm_redirect_url=config.amo_config.amocrm_redirect_url,
        amocrm_client_secret=config.amo_config.amocrm_client_secret,
        amocrm_secret_code=config.amo_config.amocrm_secret_code,
        amocrm_access_token=config.amo_config.amocrm_access_token,
        amocrm_refresh_token=config.amo_config.amocrm_refresh_token
    )
    amo_api.init_oauth2()






