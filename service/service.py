import pickle

import requests

discount_types = {
    'discount_only': 'Только скидка',
    'discount_and_spend_points': 'Скидка и списать бонусы',
    'accumulate_points': 'Накопить бонусы'
}


class Order:
    def __init__(self, raw_json: dict, lead_id: int):
        self.raw_json = raw_json
        self.lead_id = lead_id
        self.phone = raw_json.get('phone')
        self.order_type = raw_json.get('type')

    def get_order_message(self, service=True):
        use_previous = self.raw_json.get('usePreviousOrder', '')
        order_type = self.raw_json.get('type')
        if order_type == 'commercial_offer':
            service_header = f'Запрос КП №{self.lead_id}\n\n'
            client_header = f'Вы запросили КП №{self.lead_id}\n\n'
        else:
            service_header = f'Запрос счета №{self.lead_id}\n\n'
            client_header = f'Вы запросили счет №{self.lead_id}\n\n'

        customer_phone = f'Телефон получателя: {self.phone}\n'
        order_items = self.get_items()
        delivery_message = self.get_delivery_message()
        discount_types = self.discount_type()
        payment_details = self.get_payment_details()
        work_schedule = ('Менеджер партнерского отдела примет заказ в работу и свяжется с вами в рабочее время'
                         ' для уточнения деталей (Пн-Пт, с 09 до 18 по мск.')

        previous_message = 'Заполнить по прошлому заказу реквизиты, способ оплаты, получателя и адрес доставки!\n' if use_previous else ''

        response_message = order_items + customer_phone + previous_message + delivery_message + payment_details + discount_types
        if service:
            response_message = service_header + response_message
        else:
            response_message = client_header + response_message + work_schedule
        return response_message
    def get_delivery_message(self):
        delivery_method = self.raw_json.get('deliveryMethod', '')
        delivery_adress = self.raw_json.get('pickupAddress', '') + self.raw_json.get('deliveryAddress', '')
        delivery_response = (f'Тип доставки: {delivery_method}\n'
                    f'Адрес доставки: {delivery_adress}\n')
        return delivery_response

    def get_items(self):
        response = 'Состав заказа:\n'
        items = self.raw_json.get('items')
        for item in items:
            name = item.get('name')
            modify = item.get('modificationName')
            modify = modify if modify != name else ''

            quantity = item.get('quantity')
            total = item.get('total')
            price = item.get('price')
            response += f'{name} {modify}, {price} руб. x {str(quantity)} шт. = {str(total)} руб.\n'
        response += f'Сумма: {self.raw_json.get("total")} руб.\n\n'
        return response

    def get_payment_details(self):
        payment_type = self.raw_json.get('paymentMethod', '')
        organizationInn = self.raw_json.get('organizationInn', '')
        organizationAddress = self.raw_json.get('organizationAddress', '')
        organizationBik = self.raw_json.get('organizationBik', '')
        organizationAccount = self.raw_json.get('organizationAccount', '')
        response_payments = f'Тип оплаты: {payment_type}\n' if payment_type else ''
        if payment_type == 'Счет на оплату':
            payment_details = (f'Реквизиты:\n'
                               f'ИНН: {organizationInn}\n'
                               f'Юр.адрес: {organizationAddress}\n'
                               f'Бик: {organizationBik}\n'
                               f'Р\с: {organizationAccount}\n')
            response_payments += payment_details

        return response_payments

    def discount_type(self):
        discount_type = self.raw_json.get('discountType')
        discount = discount_types[discount_type]
        discount_message = f'Что делать с бонусами: {discount}\n\n'
        return discount_message

    def get_fields_for_lead(self):
        data = {
            'payment_type': self.get_payment_method(),
            'delivery_type': f'{self.get_delivery_type()}',
            'delivery_adress': self.raw_json.get('deliveryAddress', ''),
            'inn': self.raw_json.get('organizationInn', ''),
            'bik': self.raw_json.get('organizationBik', ''),
            'organization_account': self.raw_json.get('organizationAccount', ''),
            'organization_adress': self.raw_json.get('organizationAddress', ''),
        }
        return data


    def get_delivery_type(self):
        deliveryMethod = self.raw_json.get('deliveryMethod', '')
        if deliveryMethod == 'Самовывоз':
            return 'Офис'
        else:
            return 'Я.Доставка'

    def get_payment_method(self):
        payment_type = self.raw_json.get('paymentMethod', '')
        if payment_type == 'Ссылка на оплату картой':
            return True
        else:
            return False


class LeadData: # Класс описывает подготовку и передачу json с полями сделки для передачи в АМО
    def __init__(self, raw_json, fields_id):
        self.raw_json = raw_json
        self.fields_id = fields_id
        self.custom_fields = fields_id.get('lead_custom_fields')

    def get_discount(self): # Заполнение поля скидка в заказе
        discount_type = self.raw_json.get('discountType', '')
        discount_percent = self.raw_json.get('discont', '0')
        if discount_type in ('discount_only', 'discount_and_spend_points'):
            return str(discount_percent)
        elif discount_type == 'accumulate_points':
            return '0'
        else:
            return '0'

    def get_delivery_type(self):
        deliveryMethod = self.raw_json.get('deliveryMethod', '')
        if deliveryMethod == 'Самовывоз':
            return 'Офис'
        else:
            return 'Я.Доставка'

    def get_discount_data(self):
        discount_value = self.get_discount()
        data = {
                    'field_id': self.custom_fields.get('discount_field'), # Поле скидки в сделке
                    'values': [
                        {
                            'value': discount_value
                        }]
                }
        return data

    def get_delivery_data(self):
        data = {"field_id": self.custom_fields.get('delivery_type'),  # Поле склад
                 "values": [
                     {"value": self.get_delivery_type()},
                 ]
                 }
        return data

    def get_delivery_adress_data(self):
        data = {"field_id": self.custom_fields.get('delivery_adress'),  # Поле адрес доставки
                 "values": [
                     {'enum_code': 'address_line_1',
                      'enum_id': 1,
                      'value': self.raw_json.get('deliveryAddress', '')}
                 ]
                 }
        return data

    def get_need_manager_checkbox(self):
        value = self.raw_json.get('HelpManagerNeed', False)
        data = {
                    'field_id': self.custom_fields.get('need_manager_checkbox'), # Чекбокс оплаты картой
                    'values': [
                        {
                            'value': value
                        }
                    ]}
        return data

    def get_inn_data(self):
        inn_field_id = self.custom_fields.get('inn')
        inn_value = self.raw_json.get('inn', '')
        data = {"field_id": inn_field_id,  # Поле ИНН
                 "values": [
                     {"value": inn_value},
                 ]
                 }
        return data

    def get_bik_data(self):
        bik_field_id = self.custom_fields.get('bik')
        bik_value = self.raw_json.get('bik', '')
        data = {"field_id": bik_field_id,  # Поле Бик
                 "values": [
                     {"value": bik_value},
                 ]
                 }
        return data

    def get_organization_account_data(self):
        organization_account_field_id = self.custom_fields.get('organization_account')
        organization_account_value = self.raw_json.get('organization_account', '')
        data = {"field_id": organization_account_field_id,  # Поле Р\с
                 "values": [
                     {"value": organization_account_value},
                 ]}
        return data

    def get_organization_adress_data(self):
        organization_adress_field_id = self.custom_fields.get('organization_adress')
        organization_adress_value = self.raw_json.get('organization_adress', '')
        data = {"field_id": organization_adress_field_id,  # Поле Бик
                 "values": [
                     {"value": organization_adress_value},
                 ]}
        return data

    def get_kard_pay_data(self):
        payment_type = self.raw_json.get('paymentMethod', '')
        if payment_type == 'Ссылка на оплату картой':
            flag = True
        else:
            flag = False
        data = {
                    'field_id': self.custom_fields.get('kard_pay'), # Чекбокс оплаты картой
                    'values': [
                        {
                            'value': flag
                        }
                    ]}
        return data

    def get_project_name_data(self):
        project_field_id = self.custom_fields.get('partner_project_id')
        data = {"field_id": project_field_id,  # Поле проект
                 "values": [
                     {"value": 'Выклы и УД (Партнеры)'},
                 ]
                 }
        return data

    def get_appeal_type(self):
        appeal_type_field_id = self.custom_fields.get('appeal_type_field_id')
        data = {"field_id": appeal_type_field_id,  # Поле проект
                 "values": [
                     {"value": 'Повторное'},
                 ]
                 }
        return data

    def get_lead_target_data(self):
        lead_target_data = self.custom_fields.get('lead_target_field_id')
        data = {"field_id": lead_target_data,  # Поле проект
                 "values": [
                     {"value": 'Индивид. задача'},
                 ]
                 }
        return data

    def get_custom_fields_data(self):
        custom_fields_data = []
        custom_fields_data.append(self.get_discount_data())
        custom_fields_data.append(self.get_delivery_data())
        custom_fields_data.append(self.get_delivery_adress_data())
        custom_fields_data.append(self.get_inn_data())
        custom_fields_data.append(self.get_bik_data())
        custom_fields_data.append(self.get_organization_account_data())
        custom_fields_data.append(self.get_organization_adress_data())
        custom_fields_data.append(self.get_kard_pay_data())
        custom_fields_data.append(self.get_project_name_data())
        custom_fields_data.append(self.get_appeal_type())
        custom_fields_data.append(self.get_lead_target_data())
        custom_fields_data.append(self.get_need_manager_checkbox())
        return custom_fields_data

    def get_lead_tags(self):
        chat_bot_tag_id = self.fields_id.get('tag_id')
        need_help_tag = self.fields_id.get('need_help_tag')
        tag_list = [chat_bot_tag_id]
        if self.raw_json.get('HelpManagerNeed', False):
            tag_list.append(need_help_tag)

        data = [{
            'id': value
        } for value in tag_list]
        return data

def get_lead_total(record):
    field_total_id = 1105084
    field_type_id = 1105600
    fields_values = record.get('custom_fields_values')
    value = 0
    record_type = ''
    for field in fields_values:
        if field.get('field_id') == field_total_id:
            value = field.get('values')[0].get('value')
        if field.get('field_id') == field_type_id:
            record_type = field.get('values')[0].get('value')
    if record_type == 'Возврат':
        return -int(value)
    else:
        return int(value)


def get_bonus_total(record):
    field_total_id = 1105086
    fields_values = record.get('custom_fields_values')
    value = 0
    for field in fields_values:
        if field.get('field_id') == field_total_id:
            value = field.get('values')[0].get('value')
            return int(value)


# Принимает на вход id сделки и возвращает файл с КП по данному заказу
def get_kp_pdf(lead_id: int):
    pdf_response = requests.get(url=f'https://process.connect-profi.ru/amocrm/actions/get_kp/index.php?leadId={lead_id}&methodKey=vikl')
    with open(f'Kp_{lead_id}.pdf', 'wb') as f:
        pickle.dump(pdf_response.content, f)


