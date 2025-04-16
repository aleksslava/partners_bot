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
        self.custom_fields = kwargs.get('custom_fields_values')
        self.phone_list = None
        self.mail_list = None

    def _get_phone_number_list(self, custom_fields_dict):
        pass

    def _get_mail_list(self, custom_fields_dict):
        pass


class Customer:
    # Список доступных статусов партнёра
    partner_status_dct: dict[str, list] = {
        'Старт': ['скидка 15%', 0],
        'Бронза': ['скидка 20%', 100],
        'Серебро': ['скидка 30%', 500000],
        'Золото': ['скидка 35%',],
        'Платина': ['скидка 40%',],
        'Бизнес': ['скидка 40%',]
    }

    partner_status_list: list = [
        'Старт', 'Бронза', 'Серебро', 'Золото', 'Платина', 'Бизнес'
    ]

    def __call__(self, customer_dct: dict):
        self.id = customer_dct.get('id')
        self.name = customer_dct['name']
        self.itv = customer_dct.get('itv')  # Сумма покупок партнёра
        self.custom_fields = customer_dct['custom_fields_values']
        self.manager = Customer.get_manager(self.custom_fields)
        self.status = self.get_status(self.custom_fields)
        self.bye_in_this_period = Customer.bye_this_period(self.custom_fields)
        self.bonuses = Customer.get_bonuses(self.custom_fields)
        self.town = Customer.get_town(self.custom_fields)
        self.next_status = self.get_next_status(self.status)
        # self.bye_for_next_status = pass

        return self


    @staticmethod
    def get_manager(values: list):
        manager = [res for res in values if res['field_id'] == 1506979][0]
        manager_value = manager.get('values')[0].get('value')
        return manager_value

    def get_status(self, values: list):
        status = [res for res in values if res['field_id'] == 1506981][0]
        status_value: str = status.get('values')[0].get('value').split()[0]
        return f'{status_value}, {self.partner_status_dct.get(status_value)[0]}'

    @staticmethod
    def bye_this_period(values: list):
        summ = [res for res in values if res['field_id'] == 1506983][0]
        summ_value = summ.get('values')[0].get('value')
        return summ_value

    @staticmethod
    def get_bonuses(values: list):
        bonuses = [res for res in values if res['field_id'] == 1506985][0]
        bonuses_value = bonuses.get('values')[0].get('value')
        return bonuses_value

    @staticmethod
    def get_town(values: list):
        town = [res for res in values if res['field_id'] == 1506989][0]
        town_value = town.get('values')[0].get('value')
        return town_value

    def get_next_status(self, partner_status):
        for index, status in enumerate(self.partner_status_list):
            if status in partner_status.split()[0]:
                ind = index

        if len(self.partner_status_list) == ind + 1:
            next_status = partner_status
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
        access_token = response["access_token"]
        refresh_token = response["refresh_token"]

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
            customer_id = customer_list[0]['id']
            url = f'/api/v4/customers/{customer_id}'
            customer = self._base_request(endpoint=url, type='get').json()

            return True, customer
        else:
            return contact

    def get_customer_by_id(self, customer_id, with_contacts=False) -> tuple:
        url = f'/api/v4/customers/{customer_id}'
        if with_contacts:
            query = str(f'with=contacts')
            customer = self._base_request(endpoint=url, type='get_param', parameters=query)
        else:
            customer = self._base_request(endpoint=url, type='get')
        if customer.status_code == 200:
            return True, customer.json()
        elif customer.status_code == 204:
            return False, 'Партнёр не найден!'
        else:
            logger.error('Нет авторизации в AMO_API')
            return False, 'Произошла ошибка на сервере!'

    def get_customer_by_tg_id(self, tg_id: int) -> dict:  # Нужно убрать все id полей амо в конфиг
        url = '/api/v4/customers'
        field_id = '1519847'
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

        elif response.status_code == 401:
            return {'status_code': False,
                    'tg_id_in_db': False,
                    'response': 'Произошла ошибка на сервере'
                    }

    def put_tg_id_to_customer(self, id_customer, tg_id):
        url = f'/api/v4/customers/{id_customer}'
        data = {"custom_fields_values": [
            {"field_id": 1519847,
             "values": [
                 {"value": f"{tg_id}"},
                 ]
             }]}
        response = self._base_request(type='patch', endpoint=url, data=data)
        print(response.status_code)

    def get_contact_by_id(self, contact_id):
        url = f'/api/v4/contacts/{contact_id}'
        response = self._base_request(type='get', endpoint=url)

        return response.json()





    @staticmethod
    def get_customer_params(customer_dct: dict[str, str]) -> Customer:
        customer = Customer()
        customer = customer(customer_dct)
        return customer






