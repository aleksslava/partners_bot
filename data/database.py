# Класс описывающий сущность партнёра
class Partner:
    def __init__(self,
                 customer_id: str,
                 last_name: str | None = None,
                 first_name: str | None = None,
                 phone_number: str | None = None,
                 is_partner: bool = False):
        self.customer_id = customer_id
        self.last_name = last_name
        self.first_name = first_name
        self.phone_number = phone_number
        self.is_partner = is_partner




# Словарь в котором будет храниться информация о партнёре
database: dict[str, Partner] = dict()

