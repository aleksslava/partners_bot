discount_types = {
    'discount_only': 'Только скидка',
    'discount_and_spend_points': 'Скидка и списать бонусы',
    'accumulate_points': 'Накопить бонусы'
}

# функция парсит данные заказа с webapp и преобразует в сообщение для примечания
def order_note(raw_json: dict) -> str:

    item_text = ''
    items = raw_json.get('items')
    for item in items:
        name = item.get('name')
        modify = item.get('modificationName') if item.get('modificationName') is not None else ''
        quantity = item.get('quantity')
        total = item.get('total')
        price = item.get('price')
        item_text += f'{name} ({modify}), {price} руб. x {str(quantity)} шт. = {str(total)} руб.\n'

    item_text += f'Сумма: {raw_json.get("total")} руб.\n\n'

    if raw_json.get('type') == 'commercial_offer':
        text = ('Запрос КП\n\n'
                'Состав заказа:\n') + item_text
    else:
        text = ('Запрос счета\n\n'
                'Позиции в заказе:\n') + item_text
        phone = raw_json.get('phone')
        delivery_method = raw_json.get('deliveryMethod')
        delivery_adress = raw_json.get('pickupAddress') + raw_json.get('deliveryAddress')
        type_of_payment = raw_json.get('paymentMethod')
        text += f'Тип доставки: {delivery_method}\n' + f'Адрес доставки: {delivery_adress}\n\n'
        text += f'Телефон получателя: {phone}\n'
        text += f'Тип оплаты: {type_of_payment}\n'
        if type_of_payment == 'Счет на оплату':
            organizationInn = raw_json.get('organizationInn')
            organizationAddress = raw_json.get('organizationAddress')
            organizationBik = raw_json.get('organizationBik')
            organizationAccount = raw_json.get('organizationAccount')
            text_of_payment = (f'Реквизиты:\n'
                               f'ИНН: {organizationInn}\n'
                               f'Юр.адрес: {organizationAddress}\n'
                               f'Бик: {organizationBik}\n'
                               f'Р\с: {organizationAccount}')
            text += text_of_payment
    discount_type = raw_json.get('discountType')
    discount = discount_types[discount_type]
    text += f'\nЧто делать с бонусами: {discount}'
    return text

