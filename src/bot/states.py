"""
Состояния для Finite State Machine бота
"""

from aiogram.fsm.state import State, StatesGroup


class SubscriptionStates(StatesGroup):
    """Процесс подписки на проеут"""

    choosing_platform = State()
    choosing_project = State()
    choosing_events = State()
    confirming = State()


class UnsubscriptionStates(StatesGroup):
    """Процесс отписки от проекта"""

    choosing_subscription = State()
    confirming = State()
