discount_types = {
    'discount_only': 'Только скидка',
    'discount_and_spend_points': 'Скидка и списать бонусы',
    'accumulate_points': 'Накопить бонусы'
}


class Order:
    def __init__(self, raw_json: dict, lead_id: int):
        self.raw_json = raw_json
        self.lead_id = lead_id
        self.phone = self.raw_json.get('phone')

    def get_order_message(self, service=True):
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

        response_message = order_items + customer_phone + delivery_message + payment_details + discount_types
        if service:
            response_message = service_header + response_message
        else:
            response_message = client_header + response_message + work_schedule
        return response_message
    def get_delivery_message(self):
        delivery_method = self.raw_json.get('deliveryMethod')
        delivery_adress = self.raw_json.get('pickupAddress') + self.raw_json.get('deliveryAddress')
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
        organizationInn = self.raw_json.get('organizationInn')
        organizationAddress = self.raw_json.get('organizationAddress')
        organizationBik = self.raw_json.get('organizationBik')
        organizationAccount = self.raw_json.get('organizationAccount')
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
