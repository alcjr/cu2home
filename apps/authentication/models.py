from django.db import models  # noqa: F401

# Decisión de arquitectura: NO se define un modelo de usuario propio aquí.
# El acceso al panel admin (dashboard/visor/config) usa el auth.User
# estándar de Django con is_staff=True, protegido con
# @staff_member_required en las vistas correspondientes. Ver views.py:
# StaffLoginView/StaffLogoutView reutilizan django.contrib.auth.views.
#
# Si en el futuro hace falta algo más (ej. registro de intentos fallidos,
# 2FA, campos extra del staff), lo natural es un perfil OneToOne sobre
# auth.User -- el mismo patrón que ya usa la app `users` para el portal
# público -- en vez de un modelo de usuario paralelo.
