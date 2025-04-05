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


class Customer:
    def __call__(self, customer_dct: dict):
        self.id = customer_dct.get('id')
        self.name = customer_dct['name']
        self.custom_fields = customer_dct['custom_fields_values']
        self.kval = Customer.get_kval(self.custom_fields)
        self.manager = Customer.get_manager(self.custom_fields)
        self.status = Customer.get_status(self.custom_fields)
        self.bye_after_first_april = Customer.get_bye_after_first_april(self.custom_fields)
        self.bonuses = Customer.get_bonuses(self.custom_fields)
        self.payout = Customer.get_payout_summ(self.custom_fields)
        self.town = Customer.get_town(self.custom_fields)

        return self

    @staticmethod
    def get_kval(values: list):
        kval = [res for res in values if res['field_id'] == 1506993][0]
        kval_value = kval.get('values')[0].get('value')
        is_kval = 'Активен' if kval_value == 'Да' else 'Не активен'
        return is_kval

    @staticmethod
    def get_manager(values: list):
        manager = [res for res in values if res['field_id'] == 1506979][0]
        manager_value = manager.get('values')[0].get('value')
        return manager_value

    @staticmethod
    def get_status(values: list):
        status = [res for res in values if res['field_id'] == 1506981][0]
        status_value = status.get('values')[0].get('value')
        return status_value

    @staticmethod
    def get_bye_after_first_april(values: list):
        summ = [res for res in values if res['field_id'] == 1506983][0]
        summ_value = summ.get('values')[0].get('value')
        return summ_value

    @staticmethod
    def get_bonuses(values: list):
        bonuses = [res for res in values if res['field_id'] == 1506985][0]
        bonuses_value = bonuses.get('values')[0].get('value')
        return bonuses_value

    @staticmethod
    def get_payout_summ(values: list):
        payout = [res for res in values if res['field_id'] == 1506987][0]
        payout_value = payout.get('values')[0].get('value')
        return payout_value

    @staticmethod
    def get_town(values: list):
        town = [res for res in values if res['field_id'] == 1506989][0]
        town_value = town.get('values')[0].get('value')
        return town_value


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
        return response

    # def get_lead_by_id(self, lead_id):
    #     url = "/api/v4/leads/" + str(lead_id)
    #     return self._base_request(endpoint=url, type="get")

    # def get_user_by_id(self, user_id):
    #     url = '/api/v4/user/' + str(user_id)
    #     return self._base_request(endpoint=url, type="get")
    def get_contact_by_phone(self, phone_number, with_customer=False) -> tuple:
        phone_number = str(phone_number)[2:]
        url = '/api/v4/contacts'
        if with_customer:
            query = str(f'query={phone_number}&with=customers')
        else:
            query = str(f'query={phone_number}')
        contact = self._base_request(endpoint=url, type="get_param", parameters=query)
        if contact.status_code == 200:
            return True, contact.json()['_embedded']['contacts'][0]
        elif contact.status_code == 204:
            return False, 'Контакт не найден'
        else:
            logger.error('Нет авторизации в AMO_API')
            return False, 'Произошла ошибка на сервере!'

    def get_customer_by_phone(self, phone_number) -> tuple:
        contact = self.get_contact_by_phone(phone_number, with_customer=True)
        if contact[0]:
            contact = contact[1]
            customer_id = contact['_embedded']['customers'][0]['id']
            url = f'/api/v4/customers/{customer_id}'
            customer = self._base_request(endpoint=url, type='get').json()

            return True, customer
        else:
            return contact

    def get_customer_by_id(self, customer_id) -> tuple:
        url = f'/api/v4/customers/{customer_id}'
        customer = self._base_request(endpoint=url, type='get')
        if customer.status_code == 200:
            return True, customer.json()
        elif customer.status_code == 204:
            return False, 'Контакт не найден!'
        else:
            logger.error('Нет авторизации в AMO_API')
            return False, 'Произошла ошибка на сервере!'

    @staticmethod
    def get_customer_params(customer_dct: dict[str, str]) -> Customer:
        customer = Customer()
        customer = customer(customer_dct)
        return customer


if __name__ == "__main__":
    pass



