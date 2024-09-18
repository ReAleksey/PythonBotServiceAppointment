import datetime
import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Настройка учетных данных и API
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Получение учетных данных для доступа к Google API
def get_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds



# Функция для записи события в календарь
def create_event(event_date, event_summary, event_description):
    credentials = get_credentials()
    service = build('calendar', 'v3', credentials=credentials)

    event = {
        'summary': event_summary,
        'description': event_description,
        'start': {
            'dateTime': event_date.isoformat(),
            'timeZone': 'Asia/Tashkent',  # Установлена временная зона Ташкента
        },
        'end': {
            'dateTime': (event_date + datetime.timedelta(hours=1)).isoformat(),
            'timeZone': 'Asia/Tashkent',  # Установлена временная зона Ташкента
        },
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    print('Event created: %s' % (event.get('htmlLink')))


# Функция для получения занятых временных слотов
def get_busy_slots(date):
    credentials = get_credentials()
    service = build('calendar', 'v3', credentials=credentials)

    start_of_day = datetime.datetime.combine(date, datetime.time.min).isoformat() + 'Z'
    end_of_day = datetime.datetime.combine(date, datetime.time.max).isoformat() + 'Z'

    events_result = service.events().list(calendarId='primary', timeMin=start_of_day, timeMax=end_of_day,
                                          singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])

    busy_slots = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        start_time = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).time()
        busy_slots.append(start_time)

    return busy_slots

# def get_busy_days(month_start, month_end):
#     credentials = get_credentials()
#     service = build('calendar', 'v3', credentials=credentials)
#
#     start_of_month = month_start.isoformat() + 'T00:00:00Z'
#     end_of_month = month_end.isoformat() + 'T23:59:59Z'
#
#     events_result = service.events().list(calendarId='primary', timeMin=start_of_month,
#                                           timeMax=end_of_month, singleEvents=True,
#                                           orderBy='startTime').execute()
#     events = events_result.get('items', [])
#
#     busy_days = {}
#     for event in events:
#         start = event['start'].get('dateTime', event['start'].get('date'))
#         start_date = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).date()
#         start_time = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).time()
#
#         if start_date not in busy_days:
#             busy_days[start_date] = set()
#
#         busy_days[start_date].add(start_time)
#
#     return busy_days

def get_busy_days(month_start, month_end):
    credentials = get_credentials()
    service = build('calendar', 'v3', credentials=credentials)

    start_of_month = month_start.isoformat() + 'T00:00:00Z'

    # Рассчитываем конец следующего месяца
    next_month = (month_end.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    last_day_next_month = (next_month + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    end_of_next_month = last_day_next_month.isoformat() + 'T23:59:59Z'

    events_result = service.events().list(calendarId='primary', timeMin=start_of_month,
                                          timeMax=end_of_next_month, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    busy_days = {}
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        start_date = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).date()
        start_time = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')).time()

        if start_date not in busy_days:
            busy_days[start_date] = set()

        busy_days[start_date].add(start_time)

    return busy_days
