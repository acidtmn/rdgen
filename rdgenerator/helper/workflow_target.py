class WorkflowTargetHelper:
    @staticmethod
    def should_use_selfhosted(user_secret: str, settings_secret: str, selfhosted_enabled: bool) -> bool:
        # Само наличие секрета не должно отправлять задачу в self-hosted workflow,
        # если в текущем окружении такой раннер вообще не разрешён администратором.
        if not selfhosted_enabled:
            return False

        # Пустой секрет со стороны клиента считаем отсутствием явного запроса
        # на self-hosted сборку, чтобы обычные заявки уходили в hosted workflow.
        if not user_secret:
            return False

        # Только точное совпадение секрета открывает self-hosted маршрут.
        return user_secret == settings_secret
