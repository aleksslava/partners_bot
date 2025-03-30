import pprint

import dotenv
import jwt
import requests
from datetime import datetime
import time
import logging
from requests.exceptions import JSONDecodeError
from dotenv import load_dotenv
import os

dotenv_path = os.path.join(".env")
load_dotenv(dotenv_path=dotenv_path)
load_dotenv()

subdomain = os.getenv("AMOCRM_SUBDOMAIN")
client_id = os.getenv("AMOCRM_CLIENT_ID")
client_secret = os.getenv("AMOCRM_CLIENT_SECRET")
redirect_uri = os.getenv("AMOCRM_REDIRECT_URL")
secret_code = 'def5020013d86fc5f990af3d4962e15e8dd96c108618065c85f8c25d1a30b40854e9b7883a5a8f0a60e3360e6fb3c35b76326a29d1e3cdc22be6da22fb63cd99945afd2b7ddfd5e3d67f4ed98af46a4e692647f175d15368b9bb1fbd51b1ef9ab10eb14227c17417bee6979fd8b74aee5c3877e7da5cc168b41de73a185512266501341296954b66a50f5e5ef3f49bfa6c28da0e3aeb0a893d9d60c23e79ef1ad38839b4aabb4283bd3d035f574845d6f849fe72f8a5892f3fbb5c3f25330e97ef99daea57f9b627783b5d76aeb0959b9aabd4ba7d6955e394071188f6ab54d0ea149cdb5548e2d5b225c254aef7bc5c80305065f093a4cb155ee97a8a17d741edc6caa0575d9f129b592aac1416476dfe3ba355686b43e0311466107ae900468197a86a26412627cc09e2b28507d8cea33af55edfaae5d108c940b539964855f2a8ccb435a4189656f9644523a471f2d44e7f908f11b41f2da9da9f230142a531f6070d2ae095d24d484cc8eb4c942fb023817fc94c83a9510a6815064e01d55771731daf17d88ca54525403341c82080f22049d0203b49841e2f5a1e09124bb17a1b390627499bdf7b39e1fb9085acaf5f34361ba9ac5ec40b2190b664e18673cd67e6e7531a867061e23fe35380c625f382ee90c20fa5018a39d5d414baa2247559a95757eb4a03c7483bdf8351bc32010a'


def _is_expire(token: str):
    token_data = jwt.decode(token, options={"verify_signature": False})
    exp = datetime.utcfromtimestamp(token_data["exp"])
    now = datetime.utcnow()

    return now >= exp


def _save_tokens(access_token: str, refresh_token: str):
    # Записываем в ключи .env
    os.environ["AMOCRM_ACCESS_TOKEN"] = access_token
    os.environ["AMOCRM_REFRESH_TOKEN"] = refresh_token
    dotenv.set_key(dotenv_path, "AMOCRM_ACCESS_TOKEN", os.environ["AMOCRM_ACCESS_TOKEN"])
    dotenv.set_key(dotenv_path, "AMOCRM_REFRESH_TOKEN", os.environ["AMOCRM_REFRESH_TOKEN"])


def _get_refresh_token():
    return os.getenv("AMOCRM_REFRESH_TOKEN")


def _get_access_token():
    return os.getenv("AMOCRM_ACCESS_TOKEN")


def _get_new_tokens():
    data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": _get_refresh_token(),
            "redirect_uri": redirect_uri
    }
    response = requests.post("https://{}.amocrm.ru/oauth2/access_token".format(subdomain), json=data).json()
    access_token = response["access_token"]
    refresh_token = response["refresh_token"]

    _save_tokens(access_token, refresh_token)


class AmoCRMWrapper:
    def init_oauth2(self):
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": secret_code,
            "redirect_uri": redirect_uri
        }

        response = requests.post("https://{}.amocrm.ru/oauth2/access_token".format(subdomain), json=data).json()
        print(response)
        access_token = response["access_token"]
        refresh_token = response["refresh_token"]

        _save_tokens(access_token, refresh_token)

    def _base_request(self, **kwargs) -> dict:
        if _is_expire(_get_access_token()):
            _get_new_tokens()

        access_token = "Bearer " + _get_access_token()

        headers = {"Authorization": access_token}
        req_type = kwargs.get("type")
        response = ""
        if req_type == "get":
            try:
                response = requests.get("https://{}.amocrm.ru{}".format(
                    subdomain, kwargs.get("endpoint")), headers=headers).json()
            except JSONDecodeError as e:
                logging.exception(e)

        elif req_type == "get_param":
            url = "https://{}.amocrm.ru{}?{}".format(
                subdomain,
                kwargs.get("endpoint"), kwargs.get("parameters"))
            response = requests.get(str(url), headers=headers).json()
        elif req_type == "post":
            response = requests.post("https://{}.amocrm.ru{}".format(
                subdomain,
                kwargs.get("endpoint")), headers=headers, json=kwargs.get("data")).json()
        return response

    def get_lead_by_id(self, lead_id):
        url = "/api/v4/leads/" + str(lead_id)
        return self._base_request(endpoint=url, type="get")

    def get_user_by_id(self, user_id):
        url = '/api/v4/user/' + str(user_id)
        return self._base_request(endpoint=url, type="get")

    def get_user_by_phone(self, phone_number):
        phone_number = str(phone_number)[2:]
        url = '/api/v4/contacts'
        query = str(f'query={phone_number}')
        response = self._base_request(endpoint=url, type="get_param", parameters=query)
        response = response['_embedded']['contacts'][0]['custom_fields_values']
        phone_list = [phones['values'] for phones in response if phones['field_code'] == 'PHONE']
        pprint.pprint(phone_list, indent=4)
        return response





if __name__ == "__main__":
    amocrm_wrapper_1 = AmoCRMWrapper()
    # amocrm_wrapper_1.init_oauth2()

    # print(amocrm_wrapper_1.get_lead_by_id(27280193))
    pprint.pprint(amocrm_wrapper_1.get_user_by_phone(9878217816), indent=4)






