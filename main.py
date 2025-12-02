from dotenv import load_dotenv
from background import keep_alive
import logging
from datetime import datetime
import nest_asyncio
import os
import io
from telegram.ext import CallbackContext, Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram import Update
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram import BotCommand
from telegram.ext import CallbackContext, Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import nest_asyncio
import os
import pandas as pd
from dotenv import load_dotenv
from background import keep_alive
import logging
from datetime import datetime
from collections import OrderedDict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

keep_alive()

nest_asyncio.apply()

bot_token = os.environ['TELEGRAM_BOT_TOKEN']

AUTHOR, DOC_YEAR, DOC, SCENARIO, VAR_GROUP, VAR, PRED = range(7)

month_order = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 
               'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

def log_user_action(update, action, context):
    user = update.effective_user
    user_info = f"ID: {user.id}, Username: {user.username}, First Name: {user.first_name}"
    message = f"User {user_info} - Action: {action} - Text: '{update.message.text}'"
    
    if context and context.user_data:
        current_state = f"Current state: {list(context.user_data.keys())}"
        message += f" - {current_state}"
    
    logger.info(message)

def get_unique_authors(directory):
    """
    Возвращает список уникальных авторов - названий папок в директории
    """
    unique_authors = set()
    
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Директория '{directory}' не существует")
    
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            unique_authors.add(item)
    
    unique_authors = sorted(unique_authors)
    
    return unique_authors

def get_unique_doc_years(author):
    """
    Возвращает список уникальных годов - названий папок для прогнозов выбранного автора
    """
    unique_years = set()
    directory = f"Данные/{author}"
    
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Директория '{directory}' не существует")
    
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            unique_years.add(item)
    
    unique_years = list(map(str, sorted(map(int, unique_years), reverse=True)))
    
    return unique_years

def get_doc_types_keyboard(author, year):
    """
    Возвращает список уникальных названий документов для конкретного года
    """
    num = 0
    directory = f"Данные/{author}/{year}"

    if not os.path.exists(directory):
        raise FileNotFoundError(f"Директория '{directory}' не существует")

    keyboard_doc_types = []
    if author == "Банк России":
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if os.path.isdir(full_path):
                if item == 'ОНДКП':
                    keyboard_doc_types = keyboard_doc_types + [[item]]

        b_doc_types = []
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if os.path.isdir(full_path):
                if 'Базовый прогноз' in item.partition('-')[0]:
                    b_doc_types.append((item.split('-')[0] + '-' + item.split('-')[2].split('.')[0], int(item.split('-')[1]) - 1))
        b_doc_types = list(map(lambda x: x[0], sorted(b_doc_types, key=lambda x: x[1])))
        b_doc_types = [b_doc_types[i:i+2] for i in range(0, len(b_doc_types), 2)]
        keyboard_doc_types = keyboard_doc_types + b_doc_types

        k_doc_types = []
        for item in os.listdir(directory):
            if item.partition('-')[0] == 'Краткосрочный прогноз':
                k_doc_types.append((item.split('-')[0] + '-' + item.split('-')[2].split('.')[0], int(item.split('-')[1]) - 1))
        k_doc_types = list(map(lambda x: x[0], sorted(k_doc_types, key=lambda x: x[1])))
        k_doc_types = [k_doc_types[i:i+2] for i in range(0, len(k_doc_types), 2)]
    
        keyboard_doc_types = keyboard_doc_types + k_doc_types

    elif author == "Минфин":
        for item in os.listdir(directory):
            keyboard_doc_types = keyboard_doc_types + [[item.split('.')[0]]]

    elif author == "МЭР":
        doc_types = []
        for item in os.listdir(directory):
            doc_types = doc_types + [item.split('.')[0]]
            doc_types = sorted(doc_types)
        for doci in doc_types:
            keyboard_doc_types = keyboard_doc_types + [[doci]]

    elif author == "Аналитики":
        months = []
        month_order = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 
               'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        for item in os.listdir(directory):
            months = months + [item]

        months = sorted(months, key=lambda x: month_order.index(x))
        keyboard_doc_types = [months[i:i+4] for i in range(0, len(months), 4)]
    
    return keyboard_doc_types

def get_unique_scenarios(author, year):
    unique_scenarios = set()
    directory = f"Данные/{author}/{year}/ОНДКП"
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            unique_scenarios.add(item)
    return list(unique_scenarios)

def get_var_type(author, year, doc_item, scenario):
    var_types = set()
    if doc_item == 'ОНДКП':
        directory = f"Данные/{author}/{year}/{doc_item}/{scenario}"
    elif ('Базовый прогноз' in doc_item.split('-')[0]) or (doc_item in month_order) or ('прогноз МЭР' in doc_item):
        directory = f"Данные/{author}/{year}/{doc_item}"
    for item in os.listdir(directory):
        var_types.add(item.split('.')[0])
    return sorted(list(var_types)), directory

def vars_dict_from_list(vars_list):
    vars_dict = result_dict = OrderedDict((item, item) for item in vars_list)
    replacements = [('Баланс первичных и вторичных доходов', 'Первичные и вторичные доходы'), 
                    ('Финансовый счет (искл. резервы)', 'Финансовый счет'), 
                    ('Финансовый счет (включая резервы)', 'Финансовый счет'),
                    ('Сальдо ФС по частному сектору (вкл. ошибки)', 'Сальдо ФС по частному сектору'),
                    ('Сальдо фин. операций частного сектора', 'Сальдо фин. операций частн. сектора'),
                    ('Чистое приобретение активов, искл. резервы', 'Чистое приобретение активов'),
                    ('Экспортная цена на российскую нефть', 'Цена на российскую нефть'),
                    ('Баланс консолидированного бюджета', 'Консолидированный бюджет'),
                    ('Среднегодовой уровень безработицы', 'Уровень безработицы'),
                    ('Ставка, ФРС США, верхняя граница диапазона, %, в среднем за год', 'Ставка, ФРС США, среднегодовая'),
                    ('Ставка, ЕЦБ депозитная, %, в среднем за год', 'Ставка, ЕЦБ, среднегодовая'),
                    ('Базовые нефтегазовые доходы', 'Баз. нефтегаз. доходы'),
                    ('Дополнительные нефтегазовые доходы', 'Доп. нефтегаз. доходы')
                   ]
    for old, new in replacements:
        if old in vars_dict:
            vars_dict[new] = result_dict.pop(old)
    return result_dict

async def start(update, context):
    log_user_action(update, "Start command", context)
    context.user_data.clear()
    authors = get_unique_authors('Данные')
    keyboard = [authors[i:i+2] for i in range(0, len(authors), 2)]
    reply_markup_year = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Привет! Я бот, который помнит числа из официальных прогнозов. Чьи прогнозы Вас интересуют?",
        reply_markup = reply_markup_year
    )
    
    return AUTHOR

async def author_received(update, context):
    log_user_action(update, "Year selected", context)
    authors = get_unique_authors('Данные')
    if update.message.text not in authors and update.message.text!='↩️Возврат к выбору года':
        keyboard = [authors[i:i+2] for i in range(0, len(authors), 2)]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Пожалуйста, выберите автора прогнозов из предложенных вариантов:",
            reply_markup=reply_markup
        )
        return AUTHOR

    if update.message.text!='↩️Возврат к выбору года':
        author = update.message.text
        context.user_data['author'] = author

    years = get_unique_doc_years(context.user_data['author'])
    keyboard = []
    if context.user_data['author'] == "Банк России":
        keyboard = [['Последний базовый прогноз']]
    keyboard = keyboard + [years[i:i+3] for i in range(0, len(years), 3)] + [['↩️Возврат к выбору автора прогноза']]
    reply_markup_year = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Вы выбрали автора прогноза - {context.user_data['author']}. Документ какого года Вас интересует?", 
        reply_markup = reply_markup_year)

    context.user_data['year'] = '-'
    return DOC_YEAR

async def year_received(update, context):
    log_user_action(update, "Year selected", context)

    if update.message.text == '↩️Возврат к выбору автора прогноза':
        return await start(update, context)

    context.user_data['var'] = '-'
    years = get_unique_doc_years(context.user_data['author'])
    if update.message.text not in years and update.message.text!='↩️Возврат к выбору документа':
        if (update.message.text=='Последний базовый прогноз') and (context.user_data['author'] == 'Банк России'):
            pass
        else:
            keyboard = []
            if context.user_data['author'] == "Банк России":
                keyboard = [['Последний базовый прогноз']]
            keyboard = keyboard + [years[i:i+3] for i in range(0, len(years), 3)] + [['↩️Возврат к выбору автора прогноза']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Пожалуйста, выберите год из предложенных вариантов:",
                reply_markup=reply_markup
            )
            return DOC_YEAR

    if update.message.text!='↩️Возврат к выбору документа' and update.message.text!='Последний базовый прогноз':
        year = update.message.text
        context.user_data['year'] = year

    elif update.message.text == 'Последний базовый прогноз':
        max_year = str(max(map(int, get_unique_doc_years(context.user_data['author']))))
        imax = 0
        docmax =''
        context.user_data['year'] = max_year
        directory_year = f"Данные/{context.user_data['author']}/{context.user_data['year']}"
        for item in os.listdir(directory_year):
            full_path = os.path.join(directory_year, item)
            if os.path.isdir(full_path):
                if 'Базовый прогноз' in item.partition('-')[0]:
                    if int(item.partition('-')[2].partition('-')[0]) > imax:
                        imax = int(item.partition('-')[2].partition('-')[0])
                        docmax = item.partition('-')[0] + '-' + item.partition('-')[2].partition('-')[2]
                        doc_item_max = item
        context.user_data['doc'] = docmax
        context.user_data['doc_item'] = doc_item_max
        context.user_data['var'] = 'all'
        return await doc_type_received(update, context)

    keyboard = get_doc_types_keyboard(context.user_data['author'], context.user_data['year']) + [['↩️Возврат к выбору года']]
    reply_markup_doc_type = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    if (context.user_data['author'] == "Банк России") or (context.user_data['author'] == "Минфин") or (context.user_data['author'] == "МЭР"):
        text = f"Вы выбрали прогноз {context.user_data['author']} за {context.user_data['year']} год. Какой документ Вам нужен?"
    elif context.user_data['author'] == "Аналитики":
        text = f"Какому СД за {context.user_data['year']} год предшествует прогноз аналитиков?"
    
    await update.message.reply_text(text, reply_markup = reply_markup_doc_type)

    context.user_data['doc'] = '-'
    return DOC

async def doc_type_received(update, context):
    log_user_action(update, "Doc_type selected", context)
    if update.message.text == '↩️Возврат к выбору года':
        return await author_received(update, context)
    
    keyboard = get_doc_types_keyboard(context.user_data['author'], context.user_data['year'])
    docs = sum(keyboard, [])
    keyboard = keyboard + [['↩️Возврат к выбору года']]
    if (update.message.text not in docs) and (update.message.text != 'Последний базовый прогноз'):
        if update.message.text == '↩️Возврат к выбору сценария' and context.user_data['doc'] == 'ОНДКП':
            pass
        else: 
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            if (context.user_data['author'] == "Банк России") or (context.user_data['author'] == "Минфин") or (context.user_data['author'] == "МЭР"):
                text = "Пожалуйста, выберите документ из предложенных вариантов:"
            elif context.user_data['author'] == "Аналитики":
                text = f"Пожалуйста, выберите, какому СД за {context.user_data['year']} год предшествует прогноз аналитиков из предложенных вариантов:"
                
            await update.message.reply_text(text, reply_markup=reply_markup)
            return DOC

    if context.user_data['doc'] == '-':
        doc_type = update.message.text
        context.user_data['doc'] = doc_type
    
    directory = f"Данные/{context.user_data['author']}/{context.user_data['year']}"
    if context.user_data['doc'] == 'ОНДКП':
        context.user_data['doc_item'] = context.user_data['doc']
        buttons = sorted(get_unique_scenarios(context.user_data['author'], context.user_data['year']))
        keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)] + [['↩️Возврат к выбору документа']]
        reply_markup_doc_type = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
        await update.message.reply_text(
            f"Вы выбрали {context.user_data['doc']}-{context.user_data['year']}. Какой сценарий Вам нужен?", 
            reply_markup = reply_markup_doc_type)
    
        return SCENARIO

    elif ('Базовый прогноз' in context.user_data['doc'].split('-')[0]):
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if os.path.isdir(full_path):
                if item.split('-')[0] == context.user_data['doc'].split('-')[0] and item.split('-')[2] == context.user_data['doc'].split('-')[1]:
                    if update.message.text != 'Последний базовый прогноз':
                        context.user_data['doc_item'] = item
        return await scenario_received(update, context)

    elif (context.user_data['doc'] in month_order) or ('прогноз МЭР' in context.user_data['doc']):
        for item in os.listdir(directory):
            context.user_data['doc_item'] = context.user_data['doc']
        return await scenario_received(update, context)

    elif context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']:
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if item.split('.')[0] == context.user_data['doc'].split('.')[0]:
                context.user_data['doc_item'] = item
        return await scenario_received(update, context)
    
    elif context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if item.split('-')[0] == context.user_data['doc'].split('-')[0] and item.split('-')[2].split('.')[0] == context.user_data['doc'].split('-')[1]:
                context.user_data['doc_item'] = item
        return await scenario_received(update, context)


async def scenario_received(update, context):
    log_user_action(update, "Scenario selected", context)
    if update.message.text == '↩️Возврат к выбору документа':
        return await year_received(update, context)
    if context.user_data['doc'] == 'ОНДКП':
        scenarios = sorted(get_unique_scenarios(context.user_data['author'], context.user_data['year']))
        if update.message.text not in scenarios  and update.message.text != 'Выбрать другой набор переменных' and update.message.text != '↩️Возврат к выбору набора переменных':
            keyboard = [scenarios[i:i+2] for i in range(0, len(scenarios), 2)] + [['↩️Возврат к выбору документа']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
            "Пожалуйста, выберите сценарий из предложенных вариантов:",
            reply_markup=reply_markup
            )
            return SCENARIO

        if update.message.text != 'Выбрать другой набор переменных' and update.message.text != '↩️Возврат к выбору набора переменных':
            scenario = update.message.text
            context.user_data['scenario'] = scenario
        
        var_types, path = get_var_type(context.user_data['author'], context.user_data['year'], context.user_data['doc_item'], context.user_data['scenario'])
        context.user_data['path_folders'] = path

        var_types = sorted(var_types, reverse=True)
        keyboard = [[type] for type in var_types] + [['↩️Возврат к выбору сценария']]
        reply_markup_year = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"Вы выбрали сценарий \"{context.user_data['scenario']}\" из {context.user_data['doc']}-{context.user_data['year']}. Переменные из какого набора Вас интересуют?", 
            reply_markup = reply_markup_year)
        
        return VAR_GROUP

    
    elif ('Базовый прогноз' in context.user_data['doc'].split('-')[0]) or (context.user_data['doc'] in month_order) or ('прогноз МЭР' in context.user_data['doc']):
        context.user_data['scenario'] = '-'
        var_types, path = get_var_type(context.user_data['author'], context.user_data['year'], context.user_data['doc_item'], context.user_data['scenario'])
        context.user_data['path_folders'] = path

        var_types = sorted(var_types, reverse=True)
        if context.user_data['var'] == 'all':
            keyboard = [[type] for type in var_types] + [['↩️Возврат к выбору года']]
        else:
            keyboard = [[type] for type in var_types] + [['↩️Возврат к выбору документа']]
        reply_markup_year = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"Вы выбрали {context.user_data['doc']}-{context.user_data['year']}. Переменные из какого набора Вас интересуют?", 
            reply_markup = reply_markup_year)  
        
        return VAR_GROUP
        

    elif (context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз') or (context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']):
        context.user_data['scenario'] = '-'
        context.user_data['path_folders'] = f"Данные/{context.user_data['author']}/{context.user_data['year']}/{context.user_data['doc_item']}"
        
        return await var_group_received(update, context)

async def var_group_received(update, context):
    log_user_action(update, "Var_group selected", context)
    if context.user_data['doc'] == 'ОНДКП':
        if update.message.text == '↩️Возврат к выбору сценария':
            return await doc_type_received(update, context)
    elif (update.message.text == '↩️Возврат к выбору документа') and (context.user_data['var'] != 'all'):
        return await year_received(update, context)
    elif (update.message.text == '↩️Возврат к выбору года') and (context.user_data['var'] == 'all'):
        return await author_received(update, context)
        
    if context.user_data['doc'] == 'ОНДКП':
        var_types, path = get_var_type(context.user_data['author'], context.user_data['year'], context.user_data['doc_item'], context.user_data['scenario'])
        if update.message.text not in var_types and update.message.text != 'Выбрать другую переменную':
            var_types = sorted(var_types, reverse=True)
            keyboard = [[type] for type in var_types] + [['↩️Возврат к выбору сценария']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
            "Пожалуйста, выберите группу переменных из предложенных вариантов:",
            reply_markup=reply_markup
            )
            return VAR_GROUP
    
    elif ('Базовый прогноз' in context.user_data['doc'].split('-')[0]) or (context.user_data['doc'] in month_order) or ('прогноз МЭР' in context.user_data['doc']):
        var_types, path = get_var_type(context.user_data['author'], context.user_data['year'], context.user_data['doc_item'], context.user_data['scenario'])
        if update.message.text not in var_types and update.message.text != 'Выбрать другую переменную':
            var_types = sorted(var_types, reverse=True)
            if context.user_data['var'] == 'all':
                keyboard = [[type] for type in var_types] + [['↩️Возврат к выбору года']]
            else:
                keyboard = [[type] for type in var_types] + [['↩️Возврат к выбору документа']]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
            "Пожалуйста, выберите группу переменных из предложенных вариантов:",
            reply_markup=reply_markup
            )
            return VAR_GROUP

    if (context.user_data['doc'] == 'ОНДКП') or ('Базовый прогноз' in context.user_data['doc'].split('-')[0]) or (context.user_data['doc'] in month_order) or ('прогноз МЭР' in context.user_data['doc']):  
        if update.message.text != 'Выбрать другую переменную':
            var_group = update.message.text
            context.user_data['var_group'] = var_group
        
        for item in os.listdir(context.user_data['path_folders']):
            if item.split('.')[0] == context.user_data['var_group']:
                context.user_data['path'] = context.user_data['path_folders'] + '/' + item
    
    elif (context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз') or (context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']):
        context.user_data['var_group'] = '-'
        context.user_data['path'] = context.user_data['path_folders']
    
    df = pd.read_excel(context.user_data['path'])
    vars_list = list(df.iloc[:, 0])
    vars_dict = vars_dict_from_list(vars_list)
    vars_button_name = list(vars_dict.keys())
    
    if context.user_data['var'] == 'all':
        return await vars_received(update, context)

    if 'selected_vars' not in context.user_data:
        context.user_data['selected_vars'] = []

    keyboard = []
    for i in range(0, len(vars_button_name), 2):
        row = []
        for var in vars_button_name[i:i+2]:
            is_selected = var in context.user_data['selected_vars']
            callback_data = f"toggle_{var}"
            text = f"✅ {var}" if is_selected else var
            row.append(InlineKeyboardButton(text, callback_data=callback_data))
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton("📊 Показать прогноз", callback_data="show_selected"),
        InlineKeyboardButton("🗑️ Очистить выбор", callback_data="clear_selection")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    nav_keyboard = []
    if (context.user_data['doc'] == 'ОНДКП') or ('Базовый прогноз' in context.user_data['doc'].split('-')[0]) or (context.user_data['doc'] in month_order) or ('прогноз МЭР' in context.user_data['doc']):
        nav_keyboard = [['↩️Возврат к выбору набора переменных']]
    elif (context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз') or (context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']):
        nav_keyboard = [['↩️Возврат к выбору документа']]
    
    nav_reply_markup = ReplyKeyboardMarkup(nav_keyboard, resize_keyboard=True)
    
    message_text = ""
    if context.user_data['doc'] == 'ОНДКП':
        message_text = (
            f"Вы выбрали группу переменных \"{context.user_data['var_group']}\" из {context.user_data['doc']}-{context.user_data['year']} сценария \"{context.user_data['scenario']}\".\n\n"
            f"Выберите переменные (можно выбрать несколько):\n"
            f"✅ - уже выбрано\n"
            f"Нажмите на переменную, чтобы добавить/убрать её из выбора\n\n"
        )
    elif ('Базовый прогноз' in context.user_data['doc'].split('-')[0]) or ('прогноз МЭР' in context.user_data['doc']):
        message_text = (
            f"Вы выбрали группу переменных \"{context.user_data['var_group']}\" из {context.user_data['doc']}-{context.user_data['year']}.\n\n"
            f"Выберите переменные (можно выбрать несколько):\n"
            f"✅ - уже выбрано\n"
            f"Нажмите на переменную, чтобы добавить/убрать её из выбора\n\n"
        )
    elif (context.user_data['doc'] in month_order):
        message_text = (
            f"Вы выбрали группу переменных \"{context.user_data['var_group']}\" из прогноза аналитиков перед СД {context.user_data['doc']}-{context.user_data['year']}.\n\n"
            f"Выберите переменные (можно выбрать несколько):\n"
            f"✅ - уже выбрано\n"
            f"Нажмите на переменную, чтобы добавить/убрать её из выбора\n\n"
        )
    elif (context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз') or (context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']):
        message_text = (
            f"Вы выбрали {context.user_data['doc']}-{context.user_data['year']}.\n\n"
            f"Выберите переменные (можно выбрать несколько):\n"
            f"✅ - уже выбрано\n"
            f"Нажмите на переменную, чтобы добавить/убрать её из выбора\n\n"
        )
    message = await update.message.reply_text(message_text, reply_markup=nav_reply_markup)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Выберите переменные:", reply_markup=reply_markup)
    
    context.user_data['var_selection_message_id'] = message.message_id
        
    return VAR

async def handle_inline_selection(update, context):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("toggle_"):
        var_name = callback_data[7:]
        if var_name in context.user_data['selected_vars']:
            context.user_data['selected_vars'].remove(var_name)
        else:
            context.user_data['selected_vars'].append(var_name)
        
        df = pd.read_excel(context.user_data['path'])
        vars_list = list(df.iloc[:, 0])
        vars_dict = vars_dict_from_list(vars_list)
        vars_button_name = list(vars_dict.keys())
        
        keyboard = []
        for i in range(0, len(vars_button_name), 2):
            row = []
            for var in vars_button_name[i:i+2]:
                is_selected = var in context.user_data['selected_vars']
                callback_data = f"toggle_{var}"
                text = f"✅ {var}" if is_selected else var
                row.append(InlineKeyboardButton(text, callback_data=callback_data))
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("📊 Показать выбранные", callback_data="show_selected"),
            InlineKeyboardButton("🗑️ Очистить выбор", callback_data="clear_selection")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        selected_count = len(context.user_data['selected_vars'])
        await query.edit_message_text(
            text=f"Выберите переменные:\n\nВыбрано переменных: {selected_count}",
            reply_markup=reply_markup
        )

    elif callback_data == "show_selected":
            if not context.user_data['selected_vars']:
                await query.answer("Вы не выбрали ни одной переменной", show_alert=True)
                return
            await show_selected_vars(update, context)
            return PRED
    
    elif callback_data == "clear_selection":
        context.user_data['selected_vars'] = []
        df = pd.read_excel(context.user_data['path'])
        vars_list = list(df.iloc[:, 0])
        vars_dict = vars_dict_from_list(vars_list)
        vars_button_name = list(vars_dict.keys())
        
        keyboard = []
        for i in range(0, len(vars_button_name), 2):
            row = []
            for var in vars_button_name[i:i+2]:
                callback_data = f"toggle_{var}"
                row.append(InlineKeyboardButton(var, callback_data=callback_data))
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("📊 Показать выбранные", callback_data="show_selected"),
            InlineKeyboardButton("🗑️ Очистить выбор", callback_data="clear_selection")
        ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text="Выберите переменные:", reply_markup=reply_markup)
        await query.answer("Выбор очищен")

async def show_selected_vars(update, context):
    query = update.callback_query
    
    df = pd.read_excel(context.user_data['path'])
    vars_list = list(df.iloc[:, 0])
    vars_dict = vars_dict_from_list(vars_list)
    pred_years = list(df.columns)[1:]
    all_messages = []

    if (context.user_data['author'].split('-')[0] == "Банк России") and (context.user_data['var_group'] == "Платежный баланс"):
        list_var_rpb = ['Импорт товаров', 'Импорт услуг', 'Импорт товаров и услуг', 
                        'Финансовый счет (искл. резервы)', 'Сальдо ФС по госсектору', 
                        'Сальдо ФС по частному сектору (вкл. ошибки)', 'Сальдо ФС по частному сектору']
        list_var_change = []
        was_rpb5 = 0
        for vpb in df['Показатель']:
            if vpb in list_var_rpb:
                list_var_change.append(vpb)
            if 'Импорт' in vpb:
                vpb_im = vpb
        
        for y in pred_years:
            if df.loc[df['Показатель'] == vpb_im, y].iloc[0] < 0:
                was_rpb5 = 1
                mask = df['Показатель'].isin(list_var_change)
                df.loc[mask, y] = df.loc[mask, y] * (-1)
    
    for var in context.user_data['selected_vars']:
        if context.user_data['doc'] == 'ОНДКП':
            text = [f"Прогноз \"{vars_dict.get(var)}\" из {context.user_data['doc']}-{context.user_data['year']} сценария \"{context.user_data['scenario']}\":"]
        elif ('Базовый прогноз' in context.user_data['doc'].split('-')[0]) or (context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз') or (context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']) or (context.user_data['author'] == 'МЭР'):
            text = [f"Прогноз \"{vars_dict.get(var)}\" из {context.user_data['doc']}-{context.user_data['year']}:"]
        elif (context.user_data['author'] == 'Аналитики'):
            text = [f"Прогноз \"{vars_dict.get(var)}\" из прогноза аналитиков перед СД {context.user_data['doc']}-{context.user_data['year']}:"]

        if (context.user_data['author'] == 'Банк России'):
            min_year = df.columns[1]
            if context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
                real = pd.read_excel('Данные/Факты.xlsx', sheet_name = 'КСП')
                ind = real.columns.get_loc(df.columns[1])
                q = real.columns[ind-3:ind]
                for qi in q:
                    r = real[real['Показатель'] == vars_dict.get(var)][qi].values[0]
                    if pd.notna(r):
                        r = round(float(r), 1)
                        r = str(r).replace('.', ',')
                        text.append(f"{qi}: {r} (факт)")
                for col in df.columns[1:]:
                    v = df[df.iloc[:, 0] == vars_dict.get(var)][col].values[0]
                    v = str(v).replace('.', ',')
                    r = real[real.iloc[:, 0] == vars_dict.get(var)][col].values[0]
                    if ('факт' not in str(v)) and pd.notna(r):
                        r = round(float(r), 1)
                        r = str(r).replace('.', ',')
                        text.append(f"{col}: {v} (факт: {r})")
                    else:
                        text.append(f"{col}: {v}")
            
                
            elif context.user_data['doc'].split('-')[0] != 'Краткосрочный прогноз':
                real = pd.read_excel('Данные/Факты.xlsx', sheet_name = 'Все')
                n = real[real.iloc[:, 0] == vars_dict.get(var)]['Округление'].values[0]
                for y in range(int(min_year)-3, int(min_year)):
                    if y in real.columns:
                        r = real[real.iloc[:, 0] == vars_dict.get(var)][y].values[0]
                        if pd.notna(r):
                            r = round(float(r), n)
                            if n==0:
                                r = int(r)
                            r = str(r).replace('.', ',')
                            text.append(f"{y}: {r} (факт)")
                        
                for col in df.columns[1:]:
                    v = df[df.iloc[:, 0] == vars_dict.get(var)][col].values[0]
                    v = str(v).replace('.', ',')
                    r = real[real.iloc[:, 0] == vars_dict.get(var)][int(col)].values[0]
                    if pd.notna(v):
                        if pd.notna(r):
                            r = round(float(r), n)
                            if n==0:
                                r = int(r)
                            r = str(r).replace('.', ',')
                            text.append(f"{col}: {v} (факт: {r})")
                        else:
                            text.append(f"{col}: {v}")

        
        elif (context.user_data['author'] == 'Аналитики'):
            if var == "Долгосрочный рост ВВП":
                col = df.columns[1]
                v = df[df.iloc[:, 0] == vars_dict.get(var)][col].values[0]
                v = str(v).replace('.', ',')
                text.append(f"{v}")
            else:
                real = pd.read_excel('Данные/Факты.xlsx', sheet_name = 'Все')
                min_year = df.columns[1]
                n = real[real.iloc[:, 0] == vars_dict.get(var)]['Округление'].values[0]
                for y in range(int(min_year)-3, int(min_year)):
                    if y in real.columns:
                        r = real[real.iloc[:, 0] == vars_dict.get(var)][y].values[0]
                        if pd.notna(r):
                            r = round(float(r), n)
                            if n==0:
                                r = int(r)
                            r = str(r).replace('.', ',')
                            text.append(f"{y}: {r} (факт)")
                        
                for col in df.columns[1:]:
                    if y in real.columns:
                        v = df[df.iloc[:, 0] == vars_dict.get(var)][col].values[0]
                        v = str(v).replace('.', ',')
                        r = real[real.iloc[:, 0] == vars_dict.get(var)][int(col)].values[0]
                        if pd.notna(v):
                            if pd.notna(r):
                                r = round(float(r), n)
                                if n==0:
                                    r = int(r)
                                r = str(r).replace('.', ',')
                                text.append(f"{col}: {v} (факт: {r})")
                            else:
                                text.append(f"{col}: {v}")

        
        elif context.user_data['author'] == 'Минфин':
            if context.user_data['doc'].split('.')[0] == 'Бюджетная система (ОНБП)':
                b = 'ОНБП'
            elif context.user_data['doc'].split('.')[0] == 'Федеральный бюджет (ФЗоФБ)':
                b = 'ФЗоФБ'
            
            df1 = pd.read_excel(context.user_data['path'], sheet_name = "трлн руб")
            df2 = pd.read_excel(context.user_data['path'], sheet_name = "% ВВП")

            real1 = pd.read_excel('Данные/Факты.xlsx', sheet_name = f'{b} трлн руб')
            real2 = pd.read_excel('Данные/Факты.xlsx', sheet_name = f'{b} % ВВП')
            min_year = df1.columns[1]

            for y in range(int(min_year)-3, int(min_year)):
                if y in real1.columns:
                    r_v = real1[real1.iloc[:, 0] == vars_dict.get(var)][y].values[0]
                    if pd.notna(r_v):
                        r_v = round(float(r_v), 1)
                        r_v = str(r_v).replace('.', ',')
                        text.append(f"{y}: {r_v} трлн руб. (факт)")

            for col in df1.columns[1:]:
                v = round(float(df1[df1.iloc[:, 0] == vars_dict.get(var)][col].values[0]), 1)
                v = str(v).replace('.', ',')
                r_v = real1[real1.iloc[:, 0] == vars_dict.get(var)][int(col)].values[0]
                if pd.notna(r_v):
                    r_v = round(r_v, 1)
                    r_v = str(r_v).replace('.', ',')
                    text.append(f"{col}: {v} трлн руб. (факт: {r_v})")
                else:
                    text.append(f"{col}: {v} трлн руб.")

            text.append("")


            for y in range(int(min_year)-3, int(min_year)):
                if y in real2.columns:
                    r_p = real2[real2.iloc[:, 0] == vars_dict.get(var)][y].values[0]
                    if pd.notna(r_p):
                        r_p = round(float(r_p), 1)
                        r_p = str(r_p).replace('.', ',')
                        text.append(f"{y}: {r_p} % ВВП (факт)")

            for col in df2.columns[1:]:
                p = round(float(df2[df2.iloc[:, 0] == vars_dict.get(var)][col].values[0]), 1)
                p = str(p).replace('.', ',')
                r_p = real2[real2.iloc[:, 0] == vars_dict.get(var)][int(col)].values[0]
                if pd.notna(r_p):
                    r_p = round(r_p, 1)
                    r_p = str(r_p).replace('.', ',')
                    text.append(f"{col}: {p} % ВВП (факт: {r_p})")
                else:
                    text.append(f"{col}: {p} % ВВП")

        
        elif context.user_data['author'] == 'МЭР':
            real = pd.read_excel('Данные/Факты.xlsx', sheet_name = 'Все')
            min_year = df.columns[1]
            n = real[real.iloc[:, 0] == vars_dict.get(var)]['Округление'].values[0]
            for y in range(int(min_year)-3, int(min_year)):
                if y in real.columns:
                    r = real[real.iloc[:, 0] == vars_dict.get(var)][y].values[0]
                    if pd.notna(r):
                        r = round(float(r), n)
                        if n==0:
                            r = int(r)
                        r = str(r).replace('.', ',')
                        text.append(f"{y}: {r} (факт)")
                        
            for col in df.columns[1:]:
                v = round(float(df[df.iloc[:, 0] == vars_dict.get(var)][col].values[0]), 1)
                v = str(v).replace('.', ',')
                r = real[real.iloc[:, 0] == vars_dict.get(var)][int(col)].values[0]
                if pd.notna(v):
                    if pd.notna(r):
                        r = round(float(r), n)
                        if n==0:
                            r = int(r)
                        r = str(r).replace('.', ',')
                        text.append(f"{col}: {v} (факт: {r})")
                    else:
                        text.append(f"{col}: {v}")

        if (context.user_data['author'].split('-')[0] == "Банк России") and (context.user_data['var_group'] == "Платежный баланс"):
            text.append('* В РПБ6')

        all_messages.append("\n".join(text))

    
    await query.delete_message()
    
    for message in all_messages:
        await context.bot.send_message(chat_id=query.message.chat_id, text=message)
    
    if (context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз') or (context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']):
        keyboard = [['Выбрать другую переменную'], ['Заново'], ['Завершить']]
    else:
        keyboard = [['Выбрать другую переменную'], ['Выбрать другой набор переменных'], ['Заново'], ['Завершить']]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"Показаны прогнозы для {len(context.user_data['selected_vars'])} переменных. Выберите дальнейшее действие",
        reply_markup=reply_markup
    )


async def vars_received(update, context):
    log_user_action(update, "Var selected", context)
    
    if (context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз') or (context.user_data['doc'].split('.')[0] in ['Бюджетная система (ОНБП)', 'Федеральный бюджет (ФЗоФБ)']):
        if update.message.text == '↩️Возврат к выбору документа':
            context.user_data['selected_vars'] = []
            return await year_received(update, context)
    
    elif ('Базовый прогноз' in context.user_data['doc'].split('-')[0]) or (context.user_data['doc'].split('-')[0] == 'ОНДКП') or ('прогноз МЭР' in context.user_data['doc']) or (context.user_data['doc'] in month_order):
        if update.message.text == '↩️Возврат к выбору набора переменных':
            context.user_data['selected_vars'] = []
            return await scenario_received(update, context)
    
    df = pd.read_excel(context.user_data['path'])
    vars_list = list(df.iloc[:, 0])
    pred_years = list(df.columns)[1:]
    if (context.user_data['author'].split('-')[0] == "Банк России") and (context.user_data['var_group'] == "Платежный баланс"):
        list_var_rpb = ['Импорт товаров', 'Импорт услуг', 'Импорт товаров и услуг', 
                        'Финансовый счет (искл. резервы)', 'Сальдо ФС по госсектору', 
                        'Сальдо ФС по частному сектору (вкл. ошибки)', 'Сальдо ФС по частному сектору']
        list_var_change = []
        was_rpb5 = 0
        for vpb in df['Показатель']:
            if vpb in list_var_rpb:
                list_var_change.append(vpb)
            if 'Импорт' in vpb:
                vpb_im = vpb
        
        for y in pred_years:
            if df.loc[df['Показатель'] == vpb_im, y].iloc[0] < 0:
                was_rpb5 = 1
                mask = df['Показатель'].isin(list_var_change)
                df.loc[mask, y] = df.loc[mask, y] * (-1)
    
    if context.user_data['var'] == 'all':
        keyboard = [['Заново'], ['Выбрать другой набор переменных'], ['Завершить']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        file_name = f'{context.user_data['var_group']}-{context.user_data['doc']}-{context.user_data['year']}.xlsx'
        text = f'Направляю файл c прогнозом группы переменных {context.user_data['var_group']} из {context.user_data['doc']}-{context.user_data['year']}'
        if context.user_data['var_group'] == "Платежный баланс":
            text = text + '\n*В РПБ6'
            
        real = pd.read_excel('Данные/Факты.xlsx', sheet_name = 'Все')
        pred_columns = df.columns[1:]
        min_year = df.columns[1]
        for y in pred_columns:
            df[y] = df[y].astype(str)
            for i in range(len(df)):
                var_name = df.iloc[i]['Показатель']
                n = real[real['Показатель'] == var_name]['Округление'].values[0]
                r = real[real['Показатель'] == var_name][int(y)].values[0]
                v = str(df.loc[i,y]).replace('.', ',')
                df.loc[i,y] = str(v)
                if pd.notna(r):
                    r = round(float(r), n)
                    if n == 0:
                        r = int(r)
                    r = str(r).replace('.', ',')
                    df.loc[i,y] = str(df.loc[i,y]) + f' (факт: {r})'
        for i in range(1,4):
            df.insert(1, str(int(min_year)-i) + (' (факт)'), '-')
            for y in df.columns[1:4]:
                for i in range(len(df)):
                    var_name = df.iloc[i]['Показатель']
                    n = real[real['Показатель'] == var_name]['Округление'].values[0]
                    r = real[real['Показатель'] == var_name][int(str(y)[:4])].values[0]
                    if pd.notna(r):
                        r = round(float(r), n)
                        if n == 0:
                            r = int(r)
                        r = str(r).replace('.', ',')
                        df.loc[i,y] = str(r)
                    else:
                        if pd.notna(r):
                            r = round(float(r), n)
                            if n==0:
                                r = int(r)
                            r = str(r).replace('.', ',')
                            text.append(f"{col}: {r} (факт)")
            
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        with open(context.user_data['path'], 'rb') as file:
            await update.message.reply_document(
                document = excel_buffer,
                filename = file_name,  
                caption = text,
                reply_markup = reply_markup
            )
    
    return await pred_received(update, context)


async def pred_received(update, context):
    log_user_action(update, "Action selected", context)
    if context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        com = ['Заново', 'Выбрать другую переменную', 'Завершить']
        keyboard = [['Выбрать другую переменную'], ['Заново'], ['Завершить']]
    elif context.user_data['var'] == 'all':
        com = ['Заново', 'Выбрать другой набор переменных', 'Завершить']
        keyboard = [['Заново'], ['Выбрать другой набор переменных'], ['Завершить']]
    else:
        com = ['Заново', 'Выбрать другую переменную', 'Выбрать другой набор переменных', 'Завершить']
        keyboard = [['Выбрать другую переменную'], ['Выбрать другой набор переменных'], ['Заново'], ['Завершить']]
    
    if update.message.text not in com:
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
                "Пожалуйста, выберите команду из предложенных вариантов:",
                reply_markup=reply_markup
        )
        return PRED

    further = update.message.text
    if further == 'Заново':
        context.user_data.clear()
        return await start(update, context)
    elif further == 'Выбрать другую переменную':
        context.user_data['selected_vars'] = []
        return await var_group_received(update, context)
    elif further == 'Выбрать другой набор переменных':
        context.user_data['selected_vars'] = []
        return await scenario_received(update, context)
    elif further == 'Завершить':
        context.user_data.clear()
        await update.message.reply_text(text = 'Сессия завершена, для начала напишите /start',reply_markup = ReplyKeyboardRemove())
        return ConversationHandler.END

async def cancel(update, context) -> int:
    log_user_action(update, "Cancel", context)
    if context.user_data.get('cancelled'):
        return ConversationHandler.END
    
    await update.message.reply_text(
        'Действие отменено. Для начала введите /start',
        reply_markup=ReplyKeyboardRemove()
    )

    context.user_data['cancelled'] = True
    return ConversationHandler.END

async def set_commands(application: Application) -> None:
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("cancel", "Отменить текущее действие"),
    ]
    await application.bot.set_my_commands(commands)



async def main_async() -> None:
    application = Application.builder().token(bot_token).build()

    await set_commands(application)
    
    application.add_handler(CommandHandler("cancel", cancel), group=1)
    
    application.add_handler(CallbackQueryHandler(handle_inline_selection, pattern="^(toggle_|show_selected|clear_selection)"))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            AUTHOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, author_received)],
            DOC_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, year_received)],
            DOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, doc_type_received)],
            SCENARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, scenario_received)],
            VAR_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, var_group_received)],
            VAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, vars_received)],
            PRED: [MessageHandler(filters.TEXT & ~filters.COMMAND, pred_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    
    await application.run_polling()

def main():
    import asyncio
    asyncio.run(main_async())

if __name__ == '__main__':
    main()
