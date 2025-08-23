from telegram import Update
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove # чтобы добавить интерактивные кнопки (опции) на выбор
from telegram.ext import CallbackContext, Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import nest_asyncio
import os
import pandas as pd
from dotenv import load_dotenv
from background import keep_alive

keep_alive()

nest_asyncio.apply()

bot_token = os.environ['TELEGRAM_BOT_TOKEN']

DOC_YEAR, DOC, SCENARIO, VAR_GROUP, VAR, PRED = range(6)

def get_unique_doc_years(directory):
    """
    Возвращает список уникальных годов - названий папок в директории
    """
    unique_years = set()
    
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Директория '{directory}' не существует")
    
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            unique_years.add(item)
    
    unique_years = list(map(str, sorted(map(int, unique_years))))
    
    return unique_years

def get_unique_doc_types(year):
    """
    Возвращает список уникальных названий документов для конкретного года
    """
    doc_types = []
    num = 0
    directory = f"Данные/{year}"

    if not os.path.exists(directory):
        raise FileNotFoundError(f"Директория '{directory}' не существует")
    
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            if item == 'ОНДКП':
                num = 1
                doc_types.insert(0, item)
    
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            if item.partition('-')[0] == 'Базовый прогноз':
                doc_types.insert(int(item.split('-')[1]) - 1 + num, item.split('-')[0] + '-' + item.split('-')[2])
                num = num + 1

    for item in os.listdir(directory):
        if item.partition('-')[0] == 'Краткосрочный прогноз':
            doc_types.insert(int(item.split('-')[1]) - 1 + num, item.split('-')[0] + '-' + item.split('-')[2].split('.')[0])
    
    return doc_types

def get_doc_types_keyboard(buttons):
    keyboard = []
    row = []
    for i, button in enumerate(buttons, 1):
        row.append(button)
        if i % 2 == 0 or button == 'ОНДКП' or i == len(buttons):
            keyboard.append(row)
            row = []
    return keyboard

def get_unique_scenarios(year):
    unique_scenarios = set()
    directory = f"Данные/{year}/ОНДКП"
    for item in os.listdir(directory):
        full_path = os.path.join(directory, item)
        if os.path.isdir(full_path):
            unique_scenarios.add(item)
    return list(unique_scenarios)

def get_var_type(year, doc_item, scenario):
    var_types = set()
    if doc_item == 'ОНДКП':
        directory = f"Данные/{year}/{doc_item}/{scenario}"
    elif doc_item.split('-')[0] == 'Базовый прогноз':
        directory = f"Данные/{year}/{doc_item}"
    for item in os.listdir(directory):
        var_types.add(item.split('.')[0])
    return sorted(list(var_types)), directory

async def start(update, context):
    context.user_data.clear()
    years = get_unique_doc_years('Данные')
    keyboard = [years[i:i+3] for i in range(0, len(years), 3)]
    reply_markup_year = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Привет! Я бот, который помнит числа из официальных прогнозов. Документ какого года Вас интересует?",
        reply_markup = reply_markup_year
    )
    
    return DOC_YEAR

async def year_received(update, context):
    years = get_unique_doc_years('Данные')
    if update.message.text not in years:
        keyboard = [years[i:i+3] for i in range(0, len(years), 3)]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Пожалуйста, выберите год из предложенных вариантов:",
            reply_markup=reply_markup
        )
        return DOC_YEAR

    year = update.message.text
    context.user_data['year'] = year

    buttons = get_unique_doc_types(context.user_data['year'])
    keyboard = get_doc_types_keyboard(buttons)

    reply_markup_doc_type = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Вы выбрали {year} год. Какой документ Вам нужен?", 
        reply_markup = reply_markup_doc_type)
    
    return DOC

async def doc_type_received(update, context):
    docs = get_unique_doc_types(context.user_data['year'])
    if update.message.text not in docs:
        keyboard = get_doc_types_keyboard(docs)
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Пожалуйста, выберите документ из предложенных вариантов:",
            reply_markup=reply_markup
        )
        return DOC
    
    doc_type = update.message.text
    context.user_data['doc'] = doc_type
    
    directory = f"Данные/{context.user_data['year']}"
    if doc_type == 'ОНДКП':
        context.user_data['doc_item'] = doc_type
        buttons = get_unique_scenarios(context.user_data['year'])
        keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        reply_markup_doc_type = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
        await update.message.reply_text(
            f"Вы выбрали {context.user_data['doc']}-{context.user_data['year']}. Какой сценарий Вам нужен?", 
            reply_markup = reply_markup_doc_type)
    
        return SCENARIO
    
    elif doc_type.split('-')[0] == 'Базовый прогноз':
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if os.path.isdir(full_path):
                if item.split('-')[0] == doc_type.split('-')[0] and item.split('-')[2] == doc_type.split('-')[1]:
                    context.user_data['doc_item'] = item
        return await scenario_received(update, context)

    elif doc_type.split('-')[0] == 'Краткосрочный прогноз':
        for item in os.listdir(directory):
            full_path = os.path.join(directory, item)
            if item.split('-')[0] == doc_type.split('-')[0] and item.split('-')[2].split('.')[0] == doc_type.split('-')[1]:
                context.user_data['doc_item'] = item
        return await scenario_received(update, context)

async def scenario_received(update, context):
    if context.user_data['doc'] == 'ОНДКП':
        scenarios = get_unique_scenarios(context.user_data['year'])
        if update.message.text not in scenarios  and update.message.text != 'Выбрать другой набор переменных':
            keyboard = [scenarios[i:i+2] for i in range(0, len(scenarios), 2)]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
            "Пожалуйста, выберите сценарий из предложенных вариантов:",
            reply_markup=reply_markup
            )
            return SCENARIO

        if update.message.text != 'Выбрать другой набор переменных':
            scenario = update.message.text
            context.user_data['scenario'] = scenario
        
        var_types, path = get_var_type(context.user_data['year'], context.user_data['doc_item'], context.user_data['scenario'])
        context.user_data['path_folders'] = path

        var_types = sorted(var_types, reverse=True)
        keyboard = [[type] for type in var_types]
        reply_markup_year = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"Вы выбрали сценарий \"{context.user_data['scenario']}\" из {context.user_data['doc']}-{context.user_data['year']}. Переменные из какого набора Вас интересуют?", 
            reply_markup = reply_markup_year)
        
        return VAR_GROUP

    
    elif context.user_data['doc'].split('-')[0] == 'Базовый прогноз':
        context.user_data['scenario'] = '-'
        var_types, path = get_var_type(context.user_data['year'], context.user_data['doc_item'], context.user_data['scenario'])
        context.user_data['path_folders'] = path

        var_types = sorted(var_types, reverse=True)
        keyboard = [[type] for type in var_types]
        reply_markup_year = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            f"Вы выбрали {context.user_data['doc']}-{context.user_data['year']}. Переменные из какого набора Вас интересуют?", 
            reply_markup = reply_markup_year)  
        
        return VAR_GROUP
        

    elif context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        context.user_data['scenario'] = '-'
        context.user_data['path_folders'] = f"Данные/{context.user_data['year']}/{context.user_data['doc_item']}"
        
        return await var_group_received(update, context)

async def var_group_received(update, context):
    if context.user_data['doc'] == 'ОНДКП' or context.user_data['doc'].split('-')[0] == 'Базовый прогноз':
        var_types, path = get_var_type(context.user_data['year'], context.user_data['doc_item'], context.user_data['scenario'])
        if update.message.text not in var_types and update.message.text != 'Выбрать другую переменную':
            var_types = sorted(var_types, reverse=True)
            keyboard = [[type] for type in var_types]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
            "Пожалуйста, выберите группу переменных из предложенных вариантов:",
            reply_markup=reply_markup
            )
            return VAR_GROUP

        if update.message.text != 'Выбрать другую переменную':
            var_group = update.message.text
            context.user_data['var_group'] = var_group
        for item in os.listdir(context.user_data['path_folders']):
            if item.split('.')[0] == context.user_data['var_group']:
                context.user_data['path'] = context.user_data['path_folders'] + '/' + item
    
    elif context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        context.user_data['var_group'] = '-'
        context.user_data['path'] = context.user_data['path_folders']
    
    df = pd.read_excel(context.user_data['path'])
    vars_list = list(df.iloc[:, 0])
    
    keyboard = [vars_list[i:i+2] for i in range(0, len(vars_list), 2)]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    if context.user_data['doc'] == 'ОНДКП':
        await update.message.reply_text(
            f"Вы выбрали группу переменных \"{context.user_data['var_group']}\" из {context.user_data['doc']}-{context.user_data['year']} сценария \"{context.user_data['scenario']}\". Какая переменная Вас интересует?", 
            reply_markup = reply_markup)
    
    elif context.user_data['doc'].split('-')[0] == 'Базовый прогноз':
        await update.message.reply_text(
            f"Вы выбрали группу переменных \"{context.user_data['var_group']}\" из {context.user_data['doc']}-{context.user_data['year']}. Какая переменная Вас интересует?", 
            reply_markup = reply_markup)
    
    elif context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        await update.message.reply_text(
            f"Вы выбрали {context.user_data['doc']}-{context.user_data['year']}. Какая переменная Вас интересует?", 
            reply_markup = reply_markup)
        
    
    return VAR

async def vars_received(update, context):
    
    df = pd.read_excel(context.user_data['path'])
    vars_list = list(df.iloc[:, 0])
    if update.message.text not in vars_list:
        keyboard = [vars_list[i:i+2] for i in range(0, len(vars_list), 2)]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
                "Пожалуйста, выберите переменную из предложенного списка:",
                reply_markup=reply_markup
        )
        return VAR

    var = update.message.text
    context.user_data['var'] = var

    df = pd.read_excel(context.user_data['path'])
    pred_years = list(df.columns)[1:]

    if context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        keyboard = [['Выбрать другую переменную'], ['Заново'], ['Завершить']]
    else:
        keyboard = [['Выбрать другую переменную'], ['Выбрать другой набор переменных'], ['Заново'], ['Завершить']]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    if context.user_data['doc'] == 'ОНДКП':
        text = [f"Прогноз \"{context.user_data['var']}\" из {context.user_data['doc']}-{context.user_data['year']} сценария \"{context.user_data['scenario']}\":"]
    elif context.user_data['doc'].split('-')[0] == 'Базовый прогноз' or context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        text = [f"Прогноз \"{context.user_data['var']}\" из {context.user_data['doc']}-{context.user_data['year']}:"]
    
    for col in df.columns[1:]:
        text.append(f"{col}: {df[df.iloc[:, 0] == context.user_data['var']][col].values[0]}")
    
    await update.message.reply_text( "\n".join(text), 
            reply_markup = reply_markup)
    
    return PRED

async def pred_received(update, context):
    if context.user_data['doc'].split('-')[0] == 'Краткосрочный прогноз':
        com = ['Заново', 'Выбрать другую переменную', 'Завершить']
        keyboard = [['Выбрать другую переменную'], ['Заново'], ['Завершить']]
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
        return await start(update, context)
    elif further == 'Выбрать другую переменную':
        return await vars_received(update, context)
    elif further == 'Выбрать другой набор переменных':
        return await var_group_received(update, context)
    elif further == 'Завершить':
        await update.message.reply_text(text = 'Сессия завершена, для начала напишите /start',reply_markup = ReplyKeyboardRemove())
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get('cancelled'):
        return ConversationHandler.END
    
    await update.message.reply_text(
        'Действие отменено. Для начала введите /start',
        reply_markup=ReplyKeyboardRemove()
    )

    context.user_data['cancelled'] = True
    return ConversationHandler.END

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("cancel", "Отменить текущее действие"),
    ]
    await application.bot.set_my_commands(commands)

async def main_async() -> None:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("cancel", cancel), group=1)
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
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
