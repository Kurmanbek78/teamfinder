# TeamFinder — платформа поиска участников проектных команд

Курсовая работа по дисциплине «Проектирование и реализация серверной архитектуры (Django и Flask)».

## Возможности
- Регистрация, вход, выход; роли: автор проектов и участник
- Профили с навыками
- CRUD проектов (только автор своих проектов)
- Заявки на участие: подача, принятие и отклонение
- REST API (Django REST Framework)

## Запуск (Windows, PowerShell)
1. Создать и активировать окружение:
   python -m venv venv
   venv\Scripts\Activate.ps1
2. Установить зависимости:
   pip install -r requirements.txt
3. Создать файл `.env` в корне проекта:
   SECRET_KEY=любая-длинная-строка
   DEBUG=True
4. Применить миграции и загрузить демо-данные:
   python manage.py migrate
   python manage.py loaddata demo_data.json
5. (Необязательно) создать администратора:
   python manage.py createsuperuser
6. Запустить сервер:
   python manage.py runserver

Сайт: http://127.0.0.1:8000/
Админка: http://127.0.0.1:8000/admin/

## REST API
| Метод | Адрес | Доступ |
|-------|-------|--------|
| GET | /api/projects/ | все |
| GET | /api/projects/<id>/ | все |
| POST | /api/projects/<id>/apply/ | авторизованные |
| GET | /api/my-applications/ | авторизованные |

## Тесты
python manage.py test