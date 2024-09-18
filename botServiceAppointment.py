import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, \
    ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from google_calendar import create_event, get_busy_slots, get_busy_days


TOKEN = ''
OWNER_CHAT_ID = '78689019'  #  ID чата владельца

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Функция для генерации кнопок календаря
def generate_calendar_buttons(start_date, days_to_show=30):
    import calendar

    cal = calendar.Calendar(firstweekday=0)  # Календарь начинается с понедельника
    current_date = start_date
    buttons = []

    # Получаем занятые дни и временные слоты
    month_start = start_date.replace(day=1)
    month_end = (start_date.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    busy_days = get_busy_days(month_start, month_end)

    # Добавим название месяца
    month_name = current_date.strftime("%B %Y")
    buttons.append([InlineKeyboardButton(month_name, callback_data="ignore")])

    # Добавим дни недели
    days_of_week = ["пн.", "вт.", "ср.", "чт.", "пт.", "сб.", "вс."]
    buttons.append([InlineKeyboardButton(day, callback_data="ignore") for day in days_of_week])

    # Заполняем дни
    days_buttons = []
    for _ in range(start_date.weekday()):
        days_buttons.append(InlineKeyboardButton(" ", callback_data="ignore"))

    while current_date <= start_date + datetime.timedelta(days=days_to_show):
        is_today = current_date == datetime.date.today()
        has_available_time_slots = False

        # Проверка на занятость дня
        start_time = datetime.time(8, 0)
        end_time = datetime.time(20, 0)
        for hour in range(start_time.hour, end_time.hour):
            slot_time = datetime.datetime.combine(current_date, datetime.time(hour, 0))
            current_time = datetime.datetime.now()

            if slot_time.time() not in busy_days.get(current_date, set()) and (
                    not is_today or slot_time > current_time + datetime.timedelta(minutes=30)):
                has_available_time_slots = True
                break

        # Проверяем, если день полностью занят или это текущий день без доступных временных слотов
        if not has_available_time_slots:
            day_button = InlineKeyboardButton(" ", callback_data="ignore")
        else:
            day_button = InlineKeyboardButton(str(current_date.day),
                                              callback_data=f"date_{current_date.strftime('%Y-%m-%d')}")

        days_buttons.append(day_button)
        current_date += datetime.timedelta(days=1)
        if current_date.weekday() == 0:
            buttons.append(days_buttons)
            days_buttons = []
            if current_date.day == 1:  # Новый месяц
                month_name = current_date.strftime("%B %Y")
                buttons.append([InlineKeyboardButton(month_name, callback_data="ignore")])
                buttons.append([InlineKeyboardButton(day, callback_data="ignore") for day in days_of_week])

    if days_buttons:
        while len(days_buttons) < 7:
            days_buttons.append(InlineKeyboardButton(" ", callback_data="ignore"))
        buttons.append(days_buttons)

    return InlineKeyboardMarkup(buttons)



# Функция для генерации кнопок времени с учетом занятых слотов и прошедшего времени с отступом
def generate_time_buttons(selected_date):
    start_time = datetime.time(8, 0)
    end_time = datetime.time(20, 0)
    current_time = datetime.datetime.now()
    selected_datetime = datetime.datetime.combine(selected_date, start_time)
    end_datetime = datetime.datetime.combine(selected_date, end_time)
    busy_slots = get_busy_slots(selected_date)
    buttons = []

    # Установка отступа в 30 минут
    time_offset = datetime.timedelta(minutes=30)

    while selected_datetime < end_datetime:
        time_str = selected_datetime.strftime("%H:%M")
        if selected_datetime.time() not in busy_slots and (selected_datetime - time_offset) > current_time:
            buttons.append([InlineKeyboardButton(time_str, callback_data=f"time_{time_str}")])
        selected_datetime += datetime.timedelta(hours=1)

    return InlineKeyboardMarkup(buttons)


# Функция для создания кнопок выбора услуги
def generate_service_buttons():
    services_keyboard = [
        [InlineKeyboardButton("Маникюр", callback_data='service_manicure')],
        [InlineKeyboardButton("Педикюр", callback_data='service_pedicure')],
        [InlineKeyboardButton("Стрижка", callback_data='service_haircut')],
        [InlineKeyboardButton("Окрашивание", callback_data='service_coloring')],
        [InlineKeyboardButton("Брови", callback_data='service_eyebrows')]
    ]
    return InlineKeyboardMarkup(services_keyboard)


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Информация о салоне", callback_data='info')],
        [InlineKeyboardButton("Выбрать услугу", callback_data='choose_service')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Добро пожаловать в наш салон красоты "Женское царство"! Что бы вы хотели узнать?',
                                    reply_markup=reply_markup)


# Обработчик команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Используйте /start для начала работы с ботом.\nИспользуйте /appointment для записи на прием.')


# Обработчик команды /appointment
async def appointment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service_markup = generate_service_buttons()
    await update.message.reply_text("Пожалуйста, выберите услугу.", reply_markup=service_markup)


# Функция для отправки уведомления владельцу
async def send_owner_notification(context: ContextTypes.DEFAULT_TYPE, contact, service, date, time):
    message = (
        f"Новая запись!\n"
        f"Имя: {contact.first_name}\n"
        f"Телефон: {contact.phone_number}\n"
        f"Услуга: {service}\n"
        f"Дата: {date.strftime('%Y-%m-%d')}\n"
        f"Время: {time}"
    )
    await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=message)


# Обработчик нажатий на кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    logger.info(f"Button pressed: {query.data}")

    services_nom = {
        'manicure': 'Маникюр',
        'pedicure': 'Педикюр',
        'haircut': 'Стрижка',
        'coloring': 'Окрашивание',
        'eyebrows': 'Брови'
    }

    services_gen = {
        'manicure': 'Маникюр',
        'pedicure': 'Педикюр',
        'haircut': 'Стрижку',
        'coloring': 'Окрашивание',
        'eyebrows': 'Брови'
    }

    if query.data == 'info':
        # Отправка геопозиции
        latitude = 41.281076
        longitude = 69.305772
        await context.bot.send_location(chat_id=update.effective_chat.id, latitude=latitude, longitude=longitude)

        keyboard = [[InlineKeyboardButton("Записаться на услуги", callback_data='choose_service')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(text="Наш салон красоты предлагает широкий спектр услуг...",
                                       reply_markup=reply_markup)
    elif query.data == 'choose_service':
        service_markup = generate_service_buttons()
        await query.message.reply_text(text="Пожалуйста, выберите услугу.", reply_markup=service_markup)
    elif query.data.startswith('service_'):
        service = query.data.split('_')[1]
        context.user_data['selected_service_nom'] = services_nom[service]
        context.user_data['selected_service_gen'] = services_gen[service]
        today = datetime.date.today()
        calendar_markup = generate_calendar_buttons(today)
        await query.message.reply_text(
            text=f"Вы выбрали услугу: {services_nom[service]}.",
            reply_markup=ReplyKeyboardRemove())
        await query.message.reply_text(
            text="Пожалуйста, выберите дату для записи.",
            reply_markup=calendar_markup)
    elif query.data.startswith('date_'):
        selected_date = datetime.datetime.strptime(query.data.split('_')[1], '%Y-%m-%d').date()
        context.user_data['selected_date'] = selected_date
        time_markup = generate_time_buttons(selected_date)
        await query.message.reply_text(
            text=f"Вы выбрали дату: {selected_date}.",
            reply_markup=ReplyKeyboardRemove())
        await query.message.reply_text(
            text="Пожалуйста, выберите время.",
            reply_markup=time_markup)
    elif query.data.startswith('time_'):
        selected_time = query.data.split('_')[1]
        selected_date = context.user_data.get('selected_date')
        selected_service_nom = context.user_data.get('selected_service_nom')
        selected_service_gen = context.user_data.get('selected_service_gen')
        if not selected_date or not selected_service_nom or not selected_service_gen:
            await query.message.reply_text(text="Ошибка: не выбрана дата или услуга.",
                                           reply_markup=ReplyKeyboardRemove())
            return
        context.user_data['selected_time'] = selected_time
        contact_button = [[KeyboardButton("Поделиться контактом 📞", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(contact_button, one_time_keyboard=True, resize_keyboard=True)
        await query.message.reply_text(
            text=f"Вы выбрали время: {selected_time}.",
            reply_markup=ReplyKeyboardRemove())
        await query.message.reply_text(
            text="Пожалуйста, поделитесь вашим контактом.",
            reply_markup=reply_markup
        )


# Обработчик текстовых сообщений и контактов
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact = update.message.contact
    logger.info(f"Contact received: {contact}")
    selected_date = context.user_data.get('selected_date')
    selected_time = context.user_data.get('selected_time')
    selected_service_gen = context.user_data.get('selected_service_gen')
    selected_service_nom = context.user_data.get('selected_service_nom')
    if selected_date and selected_time and selected_service_gen and contact:
        event_datetime = datetime.datetime.strptime(f"{selected_date} {selected_time}", '%Y-%m-%d %H:%M')
        create_event(event_datetime, f"Запись на {selected_service_gen}",
                     f"Клиент: {contact.first_name}, Телефон: {contact.phone_number}")

        months = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
            7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }
        formatted_date = f"{selected_date.day} {months[selected_date.month]}"

        await update.message.reply_text(
            f"Спасибо, {contact.first_name}! Вы записаны на {selected_service_gen.lower()} {formatted_date} в {selected_time}.",
            reply_markup=ReplyKeyboardRemove())

        # Отправка уведомления владельцу
        await send_owner_notification(context, contact, selected_service_nom, selected_date, selected_time)

        context.user_data.pop('selected_date')
        context.user_data.pop('selected_time')
        context.user_data.pop('selected_service_nom')
        context.user_data.pop('selected_service_gen')
    else:
        logger.warning(
            f"Missing data: selected_date={selected_date}, selected_time={selected_time}, selected_service_gen={selected_service_gen}, contact={contact}")


# Основная функция
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("appointment", appointment_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))

    application.run_polling()


if __name__ == '__main__':
    main()
