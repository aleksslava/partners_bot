# Класс описывающий сущность партнёра
class Partner:
    def __init__(self,
                 amo_id: str,
                 last_name: str | None = None,
                 second_name: str | None = None,
                 phone_number: str | None = None,
                 is_register: bool = False):
        self.amo_id = amo_id
        self.last_name = last_name
        self.second_name = second_name
        self.phone_number = phone_number
        self.is_register = is_register




# Словарь в котором будет храниться информация о партнёре
database: dict[str, Partner] = dict()

