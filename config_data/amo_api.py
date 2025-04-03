import pprint

import dotenv
import jwt
import requests
from datetime import datetime
import logging
from requests.exceptions import JSONDecodeError
from config_data.config import load_config


class Customer:
    def __call__(self, customer_dct):
        self.id = customer_dct['id']
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
        kval = [res for res in values if res['field_id'] == '1506993'][0]
        return kval

    @staticmethod
    def get_manager(values: list):
        manager = [res for res in values if res['field_id'] == '1506979'][0]
        return manager

    @staticmethod
    def get_status(values: list):
        status = [res for res in values if res['field_id'] == '1506981'][0]
        return status

    @staticmethod
    def get_bye_after_first_april(values: list):
        summ = [res for res in values if res['field_id'] == '1506983'][0]
        return summ

    @staticmethod
    def get_bonuses(values: list):
        bonuses = [res for res in values if res['field_id'] == '1506985'][0]
        return bonuses

    @staticmethod
    def get_payout_summ(values: list):
        payout = [res for res in values if res['field_id'] == '1506987'][0]
        return payout

    @staticmethod
    def get_town(values: list):
        town = [res for res in values if res['field_id'] == '1506989'][0]
        return town




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

    def _base_request(self, **kwargs) -> dict:
        if self._is_expire(self._get_access_token()):
            self._get_new_tokens()

        access_token = "Bearer " + self._get_access_token()

        headers = {"Authorization": access_token}
        req_type = kwargs.get("type")
        response = ""
        if req_type == "get":
            try:
                response = requests.get("https://{}.amocrm.ru{}".format(
                    self.amocrm_subdomain, kwargs.get("endpoint")), headers=headers).json()
            except JSONDecodeError as e:
                logging.exception(e)

        elif req_type == "get_param":
            url = "https://{}.amocrm.ru{}?{}".format(
                self.amocrm_subdomain,
                kwargs.get("endpoint"), kwargs.get("parameters"))
            response = requests.get(str(url), headers=headers).json()
        elif req_type == "post":
            response = requests.post("https://{}.amocrm.ru{}".format(
                self.amocrm_subdomain,
                kwargs.get("endpoint")), headers=headers, json=kwargs.get("data")).json()
        return response

    def get_lead_by_id(self, lead_id):
        url = "/api/v4/leads/" + str(lead_id)
        return self._base_request(endpoint=url, type="get")

    def get_user_by_id(self, user_id):
        url = '/api/v4/user/' + str(user_id)
        return self._base_request(endpoint=url, type="get")

    def get_contact_by_phone(self, phone_number, with_customer=False):
        phone_number = str(phone_number)[2:]
        url = '/api/v4/contacts'
        if with_customer:
            query = str(f'query={phone_number}&with=customers')
        else:
            query = str(f'query={phone_number}')
        contact = self._base_request(endpoint=url, type="get_param", parameters=query)['_embedded']['contacts'][0]

        return contact

    def get_customer_by_phone(self, phone_number):
        contact = self.get_contact_by_phone(phone_number, with_customer=True)
        customer_id = contact['_embedded']['customers'][0]['id']
        url = f'/api/v4/customers/{customer_id}'
        customer = self._base_request(endpoint=url, type='get')
        pprint.pprint(customer, indent=4)
        return customer

    def get_customer_by_id(self, customer_id):
        url = f'/api/v4/customers/{customer_id}'
        customer = self._base_request(endpoint=url, type='get')
        pprint.pprint(customer, indent=4)
        return customer

    @staticmethod
    def get_customer_params(customer_dct: dict[str, str]) -> Customer:
        customer = Customer()
        customer = customer(customer_dct)
        return customer


if __name__ == "__main__":
    pass
    # amocrm_wrapper_1 = AmoCRMWrapper()
    # amocrm_wrapper_1.init_oauth2()

    # print(amocrm_wrapper_1.get_lead_by_id(27280193))
    # pprint.pprint(amocrm_wrapper_1.get_user_by_phone(9878217816), indent=4)
