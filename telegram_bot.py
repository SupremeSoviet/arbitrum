import telebot
from telebot import types
from web3 import Web3, Account
from config import *
import hashlib
import os

# Подключение к Ganache
web3 = Web3(Web3.HTTPProvider(GANACHE_RPC_URL))

bot = telebot.TeleBot(TOKEN)
standard_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
standard_markup.row(types.KeyboardButton('Проверить баланс'))
standard_markup.row(types.KeyboardButton('Отправить ETH'))
standard_markup.row(types.KeyboardButton('Загрузить файл'))
standard_markup.row(types.KeyboardButton('Проверить подлинность файла'))

db = load_db()

# Вычисление хеша файла
def calculate_file_hash(file_path):
    with open(file_path, 'rb') as file:
        file_content = file.read()
        return hashlib.sha256(file_content).hexdigest()


# Преобразование строкового хеша в bytes32
def string_to_bytes32(str_hash):
    return Web3.to_bytes(hexstr=str_hash)


# Ваша функция для проверки подлинности файла
def verify_file_hash(file_id, file_hash_str):
    file_hash_bytes32 = string_to_bytes32(file_hash_str)
    return contract.functions.verifyFileHash(file_id, file_hash_bytes32).call()


# Обработчик для получения документов
def check_docs(message):
    if message.content_type == 'text':
        if message.text == 'Отмена':
            bot.reply_to(message, 'Отменяю операцию', reply_markup=standard_markup)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
            markup.row(types.KeyboardButton('Отмена'))
            msg = bot.reply_to(message, f'Кажется, это не документ\nОтправьте файлик для проверки', reply_markup=markup)
            bot.register_next_step_handler(msg, check_docs)

    elif message.content_type != 'document':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.row(types.KeyboardButton('Отмена'))
        msg = bot.reply_to(message, 'Кажется, это не документ\nПопытайтесь отправить файлик снова', reply_markup=markup)
        bot.register_next_step_handler(msg, check_docs)

    else:
        try:
            file_info = bot.get_file(message.document.file_id)

            downloaded_file = bot.download_file(file_info.file_path)

            # Сохранение файла локально
            with open(message.document.file_name, 'wb') as new_file:
                new_file.write(downloaded_file)

            # Вычисление хеша файла
            file_hash = calculate_file_hash(message.document.file_name)

            # Проверка хеша файла в блокчейне
            is_valid = verify_file_hash(message.document.file_name, file_hash)

            # Отправка ответа пользователю
            if is_valid:
                bot.reply_to(message, "Файл подлинный.", reply_markup=standard_markup)
            else:
                bot.reply_to(message, "Файл не подлинный или не найден в блокчейне.", reply_markup=standard_markup)

            # Удаляем файл после использования
            os.remove(message.document.file_name)

        except Exception as e:
            bot.reply_to(message, f"Произошла ошибка: {e}", reply_markup=standard_markup)


def store_file_hash(file_id, file_hash, sender_private_key):
    account = Account.from_key(sender_private_key)
    nonce = web3.eth.get_transaction_count(account.address)
    txn = contract.functions.storeFileHash(
        file_id,
        Web3.to_bytes(hexstr=file_hash)  # Преобразование хеша файла в bytes32
    ).build_transaction({
        'chainId': 1337,  # Или другой chain ID
        'gas': 2000000,
        'gasPrice': web3.to_wei('50', 'gwei'),
        'nonce': nonce,
    })
    signed_txn = web3.eth.account.sign_transaction(txn, private_key=sender_private_key)
    return web3.eth.send_raw_transaction(signed_txn.rawTransaction)


def get_private_key(message) -> str:
    """
    :param message: message from telebot user
    :return: user private_key
    """
    try:
        id = message.from_user.id
        pk = db.loc[id, 'private_key']
    except:
        bot.reply_to(message, 'Кажется, вас нет в базе данных.')
        pk = False
    return pk


def get_user_address(message) -> str:
    """
    :param message: message from telebot user
    :return: user address
    """
    try:
        id = message.from_user.id
        address = db.loc[id, 'address']
    except:
        bot.reply_to(message, 'Кажется, вас нет в базе данных.')
        print(f'Пользователь {message.from_user.id}, похоже, желает добавиться в нашу сеть.')
        address = False
    return address


def get_user_name(message) -> str:
    """
    :param message: message from telebot user
    :return: user address
    """
    id = message.from_user.id
    name = db.loc[id, 'name']
    return name


def ask_for_receiver_address(message, db):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    users_list = db.name.values
    users_dict_for_markup = dict(zip(users_list.tolist(), db.address.values.tolist()))
    id_dict_for_markup = dict(zip(users_list.tolist(), db.address.index.tolist()))
    markup.row(types.KeyboardButton('Отмена'))
    for user in users_list:
        markup.row(types.KeyboardButton(f'{user}'))

    msg = bot.reply_to(message, "Выберите получателя ETH:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_receiver_address, users_dict_for_markup, id_dict_for_markup)


def get_amount(message, sender_address, sender_private_key, receiver_address, receiver_id):
    try:
        int(message.text)
        nonce = web3.eth.get_transaction_count(sender_address)
        amount = web3.to_wei(int(message.text), 'ether')
        gas_estimate = web3.eth.estimate_gas({'from': sender_address, 'to': receiver_address, 'value': amount})
        gas_price = web3.eth.gas_price

        # Создание транзакции
        tx = {
            'nonce': nonce,
            'to': receiver_address,
            'value': amount,
            'gas': gas_estimate,
            'gasPrice': gas_price
        }

        # Подписание транзакции
        signed_tx = web3.eth.account.sign_transaction(tx, sender_private_key)

        # Отправка транзакции
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # Проверка статуса транзакции
        if tx_receipt.status == 1:
            bot.reply_to(message, f'Транзакция успешно выполнена.\n\nHash: <code>{tx_hash.hex()}</code>', reply_markup=standard_markup, parse_mode='HTML')
            bot.send_message(receiver_id, f'Вам переведено {message.text} от {get_user_name(message)}')
        else:
            bot.reply_to(message, 'Ошибка при выполнении транзакции.', reply_markup=standard_markup)

    except:
        bot.reply_to(message, 'Кажется, это не число')
        msg = bot.reply_to(message, 'Давайте попробуем снова')
        bot.register_next_step_handler(msg, get_amount)


def process_receiver_address(message, users_dict, id_dict):
    if message.text == 'Отмена':
        bot.reply_to(message, 'Отменяю операцию', reply_markup=standard_markup)
    elif message.text == get_user_name(message):
        bot.reply_to(message, 'Хм... Хотите перевести денежки себе?\n\nИнтересная идея, но лучше не стоит', reply_markup=standard_markup)
    else:
        sender_address = get_user_address(message)
        sender_private_key = get_private_key(message)
        receiver_address = users_dict[message.text]
        receiver_id = id_dict[message.text]
        # Установка параметров транзакции
        msg = bot.reply_to(message, 'Введите кол-во ETH для отправки')
        bot.register_next_step_handler(msg, get_amount, sender_address, sender_private_key, receiver_address, receiver_id)


def docs_loader(message):
    if message.content_type == 'text':
        if message.text == 'Отмена':
            bot.reply_to(message, 'Отменяю операцию', reply_markup=standard_markup)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
            markup.row(types.KeyboardButton('Отмена'))
            msg = bot.reply_to(message, f'Кажется, это не документ\nОтправьте файлик для записи в блокчейн',
                               reply_markup=markup)
            bot.register_next_step_handler(msg, docs_loader)

    elif message.content_type != 'document':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.row(types.KeyboardButton('Отмена'))
        msg = bot.reply_to(message, 'Кажется, это не документ\nПопытайтесь отправить файлик снова', reply_markup=markup)
        bot.register_next_step_handler(msg, docs_loader)

    else:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            with open(message.document.file_name, 'wb') as new_file:
                new_file.write(downloaded_file)

            file_hash = calculate_file_hash(message.document.file_name)

            transaction_hash = store_file_hash(message.document.file_name, file_hash, get_private_key(message))

            bot.reply_to(message, f'Хеш файла сохранен в блокчейне.\n\nТранзакция: <code>{transaction_hash.hex()}</code>', reply_markup=standard_markup, parse_mode='HTML')

            os.remove(message.document.file_name)

        except Exception as e:
            bot.reply_to(message, f"Произошла ошибка: {e}", reply_markup=standard_markup)
            print(e)


def send_eth(message, db) -> None:
    """
    ETH sending function
    :param message: message from telebot user
    :return: None
    """
    # Запрос адреса у пользователя
    ask_for_receiver_address(message, db)


# Функция для проверки баланса
@bot.message_handler(func=lambda message: message.text == 'Проверить баланс')
def check_balance(message):
    address = get_user_address(message)
    balance = web3.eth.get_balance(address)
    eth_balance = web3.from_wei(balance, 'ether')
    bot.reply_to(message, f'Баланс: {eth_balance} ETH')


# отправка ETH
@bot.message_handler(func=lambda message: message.text == 'Отправить ETH')
def send_eth_command(message):
    # Вызов функции отправки ETH
    send_eth(message, db)


# Приветственное сообщение
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я бот для работы с Ethereum."
                          " Вы можете проверить баланс или отправить ETH.",
                 reply_markup=standard_markup)


@bot.message_handler(func=lambda message: message.text == 'Загрузить файл')
def file_blockchain_loader(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.row(types.KeyboardButton('Отмена'))
    msg = bot.reply_to(message, 'Отправьте файлик для записи в блокчейн',
                       reply_markup=markup)
    bot.register_next_step_handler(msg, docs_loader)


@bot.message_handler(func=lambda message: message.text == 'Проверить подлинность файла')
def file_blockchain_loader(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.row(types.KeyboardButton('Отмена'))
    msg = bot.reply_to(message, 'Отправьте файлик для проверки',
                       reply_markup=markup)
    bot.register_next_step_handler(msg, check_docs)


# Запуск бота
bot.infinity_polling()
