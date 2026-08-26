@echo off
python manage.py makemessages -l es --ignore=venv/* --ignore=venv --ignore="*copia*"
python manage.py makemessages -l en --ignore=venv/* --ignore=venv --ignore="*copia*"