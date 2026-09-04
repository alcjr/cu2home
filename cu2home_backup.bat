@echo off
echo Haciendo backup de cu2home_db...
"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -U postgres -W -F c -f "backup_cu2home_db_%date:~-4,4%%date:~-7,2%%date:~-10,2%.dump" cu2home_db
echo Respaldo completado.
pause