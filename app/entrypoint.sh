#!/bin/sh
set -e

# Ожидание доступности СУБД
python wait_for_db.py

# Инициализация таблиц и заполнение начальных данных
python seed.py

# Запуск веб-приложения
python app.py
