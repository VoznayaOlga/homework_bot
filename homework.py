import os
import sys
import logging
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv
from telebot import TeleBot

from homework_exception import UnexpectedAPIResponseError


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
    """Проверка наличия инициализации переменных окружения."""
    verifiable_tokens = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN',
                         'TELEGRAM_CHAT_ID')
    missing_tokens = [var_name for var_name in verifiable_tokens
                      if not globals()[var_name]]
    if missing_tokens:
        logging.critical('Отсутствует определение переменных'
                         'окружения:' + ','.join(missing_tokens))
        raise ValueError


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    logging.debug('Отправка сообщения в Telegram')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message,)
    logging.debug(message)


def get_api_answer(timestamp):
    """Запрос от api информации об изменении статуса дом.работ."""
    logging.debug('Отправка запроса к API об изменении статуса дом.работ')
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=payload)
    except requests.RequestException as error:
        raise ConnectionError(f'{ENDPOINT} {HEADERS} {payload} : {error}')

    if response.status_code != HTTPStatus.OK:
        raise UnexpectedAPIResponseError(f'{ENDPOINT} {HEADERS} {payload} :'
                                         ' {response.status_code}')
    logging.debug('Получен ответ на запрос к API')
    return response.json()


def check_response(response):
    """Проверка ответа api."""
    logging.debug('Начата проверка ответа api')
    if not isinstance(response, dict):
        raise TypeError('Данные ответа api получены в неожиданном виде,'
                        f' тип: {type(response)}')
    if 'homeworks' not in response:
        raise KeyError('Ключ homeworks отсутствует в ответе api')
    hw_type = type(response['homeworks'])
    if not isinstance(response['homeworks'], list):
        raise TypeError('Блок howeworks получен не в виде списка, '
                        f'тип {hw_type}')
    logging.debug('Проверка ответа api успешно завершена')


def parse_status(homework):
    """Получение статуса конкретной работы."""
    logging.debug('Начато получение статуса домашней работы')
    if 'homework_name' not in homework:
        raise KeyError('В блоке homework отсутствует ключ homework_name')
    if 'status' not in homework:
        raise KeyError('В блоке homework отсутствует ключ status')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS.keys():
        raise ValueError(f'Получен недокументированный статус {status} '
                         'домашней работы или статус не указан')
    verdict = HOMEWORK_VERDICTS[status]
    logging.warn(verdict)
    logging.debug('Получение статуса домашней работы завершено успешно')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_bot_message = ''

    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            check_response(response)
            homeworks = response['homeworks']
            if not homeworks:
                logging.debug('Обновлений статуса домашней работы'
                              'не зафиксировано')
                continue
            message = parse_status(homeworks[0])
            if message != last_bot_message:
                send_message(bot=bot, message=message)
                timestamp = response.get('current_date', timestamp)
                last_bot_message = message
        except (telebot.apihelper.ApiException,
                requests.exceptions.RequestException) as error:
            logging.exception(f'Сбой отправки сообщения в Telegram: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            try:
                if message != last_bot_message:
                    send_message(bot=bot, message=message)
                    last_bot_message = message
            except (telebot.apihelper.ApiException,
                    requests.exceptions.RequestException) as tb_error:
                message = (f'Сбой отправки сообщения о сбое работы программы '
                           f'в Telegram: {tb_error}')
                logging.exception(message)
        finally:
            logging.debug(f'Пауза {RETRY_PERIOD} сек')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] [%(funcName)s] '
        '[%(lineno)d] %(message)s',
        level=logging.DEBUG,
        encoding='UTF-8',
        handlers=[logging.StreamHandler(sys.stdout)])
    main()
