import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from datetime import datetime
import time
import random

session = vk_api.VkApi(token = "vk1.a.RLZ5wBztaVyxPtRX05mo8lsiA9jZTE39T_FV_9X59c-m7KDDj4lY6mcTjBOmUtQkxi3VNc1DlH0tC_bBy2hQsZeu9Z1KWjW3cLv5-msSBlxAHAdF77RxAxp4MKx23pSnVYQaIpHhYHZYulStD7m7uuFpsQnwLi6tuqdod_I2cdlYh5nux5BPcpLNUtcpV6-owUvAUphV_zodm0Sn3EgTCQ")
session_api = session.get_api()
longpoll = VkLongPoll(session)

hello = ("приветик",
         "хай",
         "хеллоу",
         "приветствую тебя",
         "здарова",
         "салют!")


memes = ("photo-197837194_457241165",
         "photo-197837194_457241070",
         "photo-197837194_457240966",
         "photo-197837194_457240900",
         "photo-197837194_457240715",
         "photo-197837194_457240702",
         "photo-114086029_457500634",
         "photo-114086029_457500403",
         "photo-114086029_457500341",
         "photo-114086029_457500344",
         "photo-191356433_457281734",
         "photo-197837194_457239064",
         "photo-197837194_457241196",
         "photo-57494037_457376190")


films = ("Лёд 2",
         "Довод",
         "Побочный эффект",
         "Соник в кино",
         "Бладшот",
         "Цвет из иных миров",
         "Реинкарнация",
         "Темный рыцарь",
         "Матрица",
         "Интерстеллар",
         "Ловец снов",
         "Бог грома",
         "Агент Ева")


kakdela = ("нормально",
           "все хорошо!!!",
           "УЖАСНО",
           "все в порядке")


chto = ("сплю",
        "ложусь спать",
        "хочу уснуть",
        "уже иду спать",
        "только проснулся",
        "с дебилом общаюсь")


bye = ("приходи еще!",
       "пока-пока!",
       "ПРОЩАЙ",
       "гудбай")


ladno = ("ЛАДНО",
         "ладно.",
         "ЛАДНО ЛАДНО")

kakzovyt = ("кабан",
            "это секрет",
            "его не зовут, он сам приходит")

dumb = ("сам такой",
        "не беси меня",
        "ацтань")

krasivi = ("а ты нет",
           "да я знаю",
           "я лучший")

bot = ("я ботттт",
       "я машина :/")

kovsh = ("photo549583246_457240237"
         "photo549583246_457240238",
         "photo549583246_457240239",
         "photo549583246_457240240",
         "photo549583246_457240241",
         "photo549583246_457240242"
         "photo549583246_457240243",
         "photo549583246_457240244",
         "photo549583246_457240245",
         "photo549583246_457240246",
         "photo549583246_457240247",
         "photo549583246_457240249",
         "photo549583246_457240250",
         "photo549583246_457240251",
         "photo549583246_457240252",
         "photo549583246_457240253",
         "photo549583246_457240254")

while True:
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            print("Cообщение пришло в: " + str(event.datetime))
            print("Текст сообщения: " + str(event.text))
            if event.from_user and not event.from_me:
                response = event.text.lower()
                if response.find("привет") >= 0 or response.find("здравствуй") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(hello), "random_id":0})

                elif response.find("пока") >= 0 or response.find("до свид") >= 0 or response.find("досвид") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(bye), "random_id":0})
                        
                elif response.find("как дел") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(kakdela), "random_id":0})
                    
                elif response.find("что делае") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(chto), "random_id":0})
                    
                elif response.find("мем") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "attachment": random.choice(memes), "random_id":0})
                    
                elif response.find("стике") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "sticker_id": 53542, "random_id":0})
                    
                elif response.find("фильм") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(films), "random_id":0})

                elif response.find("ладн") >= 0 or response.find("понятн") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(ladno), "random_id":0})

                elif response.find("как зову") >= 0 or response.find("как тебя зову") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(kakzovyt), "random_id":0})

                elif response.find("ты глупый") >= 0 or response.find("ты тупой") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(dumb), "random_id":0})

                elif response.find("ты красивый") >= 0 or response.find("ты крутой") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(krasivi), "random_id":0})

                elif response.find("кто ты") >= 0 or response.find("ты кто") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "message": random.choice(bot), "random_id":0})

                elif response.find("ковш") >= 0:
                    time.sleep(random.uniform(0.5, 1.5))
                    session.method("messages.send", {"user_id":event.user_id, "attachment": random.choice(kovsh), "random_id":0})
