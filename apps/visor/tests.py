import os
import tempfile

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


@override_settings(ROOT_URLCONF='apps.visor.urls')
class VisorViewTests(TestCase):
    """Tests para la aplicacion Visor de Logs."""

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username='staff', password='testpass', is_staff=True
        )
        cls.normal_user = User.objects.create_user(
            username='normal', password='testpass', is_staff=False
        )

    def setUp(self):
        self.client = Client()
        # Crear archivo de log temporal para tests
        self.temp_log = tempfile.NamedTemporaryFile(
            mode='w', delete=False, suffix='.log', encoding='utf-8'
        )
        self.temp_log.write(
            "INFO 2024-01-15 10:30:00,123 properties.views Propiedad creada\n"
            "DEBUG 2024-01-15 10:31:00,456 properties.models Consulta SQL\n"
            "ERROR 2024-01-15 10:32:00,789 properties.views Error grave\n"
            "WARNING 2024-01-15 10:33:00,012 core.middleware Advertencia lenta\n"
            "CRITICAL 2024-01-16 08:00:00,000 core.tasks Fallo critico\n"
            "INFO 2024-01-16 08:01:00,000 properties.views Otra info\n"
        )
        self.temp_log.close()
        self._original_log_file = getattr(settings, 'LOG_FILE', None)
        settings.LOG_FILE = self.temp_log.name

    def tearDown(self):
        if os.path.exists(self.temp_log.name):
            os.unlink(self.temp_log.name)
        if self._original_log_file:
            settings.LOG_FILE = self._original_log_file
        else:
            delattr(settings, 'LOG_FILE')

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------
    def test_visor_requires_staff(self):
        """Usuarios no-staff no pueden acceder al visor."""
        self.client.login(username='normal', password='testpass')
        response = self.client.get(reverse('visor:visor'))
        self.assertEqual(response.status_code, 302)

    def test_visor_accessible_to_staff(self):
        """Usuarios staff pueden acceder al visor."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:visor'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'visor/visor.html')

    def test_api_requires_staff(self):
        """La API de logs requiere autenticacion staff."""
        self.client.login(username='normal', password='testpass')
        response = self.client.get(reverse('visor:api'))
        self.assertEqual(response.status_code, 302)

    # ------------------------------------------------------------------
    # API de logs
    # ------------------------------------------------------------------
    def test_api_returns_json(self):
        """La API devuelve JSON con estructura esperada."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('lines', data)
        self.assertIn('total', data)
        self.assertIn('page', data)
        self.assertIn('total_pages', data)
        self.assertIn('filters', data)

    def test_api_parses_logs_correctly(self):
        """La API parsea correctamente las lineas de log."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'))
        data = response.json()
        lines = data['lines']
        self.assertEqual(data['total'], 6)

        # Verificar que se parsearon correctamente
        levels = [l['level'] for l in lines]
        self.assertIn('INFO', levels)
        self.assertIn('ERROR', levels)
        self.assertIn('CRITICAL', levels)

    def test_api_filter_by_level(self):
        """El filtro por nivel funciona correctamente."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'), {'level': 'ERROR'})
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['lines'][0]['level'], 'ERROR')

    def test_api_filter_by_search(self):
        """El filtro por texto funciona correctamente."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'), {'search': 'properties.views'})
        data = response.json()
        # Debe encontrar INFO, ERROR, INFO (3 lineas con properties.views)
        self.assertEqual(data['total'], 3)

    def test_api_filter_by_module(self):
        """El filtro por modulo funciona correctamente."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'), {'module': 'core'})
        data = response.json()
        # WARNING core.middleware y CRITICAL core.tasks
        self.assertEqual(data['total'], 2)

    def test_api_filter_by_date(self):
        """El filtro por rango de fechas funciona."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'), {
            'date_from': '2024-01-16',
            'date_to': '2024-01-16'
        })
        data = response.json()
        self.assertEqual(data['total'], 2)

    def test_api_pagination(self):
        """La paginacion funciona correctamente."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'), {'per_page': '2', 'page': '1'})
        data = response.json()
        self.assertEqual(len(data['lines']), 2)
        self.assertEqual(data['total_pages'], 3)

    def test_api_empty_log_file(self):
        """Maneja archivo de log vacio o inexistente."""
        settings.LOG_FILE = '/tmp/nonexistent_log_file_visor.log'
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:api'))
        data = response.json()
        self.assertEqual(data['total'], 0)
        self.assertIn('error', data)

    # ------------------------------------------------------------------
    # Stats API
    # ------------------------------------------------------------------
    def test_stats_api_returns_counts(self):
        """La API de estadisticas devuelve conteos por nivel."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:stats'))
        data = response.json()
        self.assertIn('stats', data)
        self.assertIn('timeline', data)
        stats = data['stats']
        self.assertEqual(stats.get('INFO'), 2)
        self.assertEqual(stats.get('ERROR'), 1)
        self.assertEqual(stats.get('CRITICAL'), 1)
        self.assertEqual(stats.get('DEBUG'), 1)
        self.assertEqual(stats.get('WARNING'), 1)

    # ------------------------------------------------------------------
    # Descarga
    # ------------------------------------------------------------------
    def test_download_requires_staff(self):
        """La descarga requiere autenticacion staff."""
        self.client.login(username='normal', password='testpass')
        response = self.client.get(reverse('visor:download'))
        self.assertEqual(response.status_code, 302)

    def test_download_returns_file(self):
        """La descarga devuelve el archivo de log."""
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:download'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertIn('attachment', response['Content-Disposition'])
        content = response.content.decode('utf-8')
        self.assertIn('Propiedad creada', content)

    def test_download_nonexistent_file(self):
        """Maneja error cuando el archivo no existe."""
        settings.LOG_FILE = '/tmp/nonexistent_log_file_visor.log'
        self.client.login(username='staff', password='testpass')
        response = self.client.get(reverse('visor:download'))
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # Parseo de lineas
    # ------------------------------------------------------------------
    def test_parse_standard_line(self):
        """Parsea lineas estandar correctamente."""
        from apps.visor.views import _parse_log_line
        line = "INFO 2024-01-15 10:30:00,123 myapp.views Mensaje de prueba"
        result = _parse_log_line(line)
        self.assertTrue(result['parsed'])
        self.assertEqual(result['level'], 'INFO')
        self.assertEqual(result['module'], 'myapp.views')
        self.assertEqual(result['message'], 'Mensaje de prueba')

    def test_parse_fallback_line(self):
        """Parsea lineas sin formato estandar como fallback."""
        from apps.visor.views import _parse_log_line
        line = "ERROR algo salio mal"
        result = _parse_log_line(line)
        self.assertFalse(result['parsed'])
        self.assertEqual(result['level'], 'ERROR')
        self.assertEqual(result['message'], 'algo salio mal')

    def test_parse_unknown_line(self):
        """Lineas sin nivel conocido se marcan como UNKNOWN."""
        from apps.visor.views import _parse_log_line
        line = "Linea sin formato reconocible"
        result = _parse_log_line(line)
        self.assertEqual(result['level'], 'UNKNOWN')

    def test_parse_empty_line(self):
        """Lineas vacias devuelven None."""
        from apps.visor.views import _parse_log_line
        self.assertIsNone(_parse_log_line(""))
        self.assertIsNone(_parse_log_line("   "))

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def test_human_readable_size(self):
        """La conversion de tamano humano funciona."""
        from apps.visor.views import _human_readable_size
        self.assertEqual(_human_readable_size(0), "0 B")
        self.assertEqual(_human_readable_size(512), "512.0 B")
        self.assertEqual(_human_readable_size(2048), "2.0 KB")
        self.assertIn("MB", _human_readable_size(5 * 1024 * 1024))
