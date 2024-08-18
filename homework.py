import os
import requests
import logging
from dotenv import load_dotenv
from telebot import TeleBot
import time


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия инициализации переменных окружения"""
    if (PRACTICUM_TOKEN is None or TELEGRAM_TOKEN is None or
            TELEGRAM_CHAT_ID is None):
        message = """Отсутствует определение одной
        или нескольких переменных окружения"""
        logging.critical(message)
        raise Exception(message)


def send_message(bot, message):
    """Отправка сообщения в Telegram"""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,)
        logging.debug(message)
    except Exception as error:
        logging.error('Ошибка отправки сообщения в Telegram.'+error)


def get_api_answer(timestamp):
    """Запрос от api информации об изменении статуса дом.работ"""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=payload)
    except Exception as error:
        logging.error(error)

    if response.status_code == 200:
        return response.json()
    else:
        err_message = 'Ошибка запроса к API'
        logging.error(err_message)
        raise Exception(err_message)


def check_response(response):
    """Проверка ответа api"""
    err_message = 'Данные в ответе api имеют неожиданную структуру'
    if 'homeworks' not in response:
        logging.error(err_message)
        raise TypeError
    if type(response['homeworks']) is not list:
        logging.error(err_message)
        raise TypeError
    return {'from_date': response['current_date'],
            'homeworks': response['homeworks']}
    #         'homework': response['homeworks'][len(response['homeworks'])-1]}


def parse_status(homework):
    """Получение статуса конкретной работы"""
    if 'homework_name' not in homework or 'status' not in homework:
        logging.error('Данные в ответе api имеют неожиданную структуру')
        raise TypeError
    homework_name = homework['homework_name']
    status = homework['status']
    if status in HOMEWORK_VERDICTS.keys():
        verdict = HOMEWORK_VERDICTS[status]
        logging.warn(verdict)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    err_message = """Получен недокументированный cnатус домашней работы
    или статус не указан"""
    logging.error(err_message)
    raise Exception(err_message)


def main():
    """Основная логика работы бота."""

    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level=logging.DEBUG,
        encoding='UTF-8',
        )
    check_tokens()
    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    # date_now = datetime.now()
    # timestamp = int(time.mktime((date_now+timedelta(days=-30)).timetuple()))

    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            res_dict = check_response(response)
            timestamp = res_dict['from_date']
            homeworks = res_dict['homeworks']
            for i, homework in enumerate(homeworks):
                message = parse_status(homework)
                send_message(bot=bot, message=message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        logging.debug(f'Пауза {RETRY_PERIOD} сек')  
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
