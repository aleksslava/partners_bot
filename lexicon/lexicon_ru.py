from config_data.amo_api import Customer

"""Модуль для русскоязычных сообщений чат бота"""


def account_info(customer: Customer):
    message = (f'<b><u>Данные Вашей учетной записи партнёра:</u></b>\n\n'
               f'👤 Имя: {customer.name}\n'
               f'🌟 Статус: {customer.status}\n'
               f'🎁 Бонусы на балансе: {customer.bonuses}\n'
               f'🌆 Город работы: {customer.town}\n'
               f'👥 Ваш менеджер: {customer.manager}\n\n'
               f'------------------------------\n\n'
               f'Следующий статус {customer.next_status}\n'
               # f'Чистый выкуп до след статуса: {customer.sales_for_next_status}'
               )
    return message


contact_message: str = (f'<b>Связаться с нами можно</b>:\n\n'
                        f'📞 <b>Телефон</b> :\n'
                        f'+7 (495) 256-33-00\n\n'
                        f'📧 <b>Электронная почта</b> :\n'
                        f'<a href="sales@hite-pro.ru">sales@hite-pro.ru</a>\n\n'
                        f'📱 <b>WhatsApp</b> :\n'
                        f'<a href="https://wa.me/79251930861">Ссылка на whatsapp</a>'
                        )

message_in_dev: str = ('Данный раздел  находится в разработке.\n'
                       'Приносим извинения за предоставленные неудобства!')





