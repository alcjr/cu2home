from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class StaffLoginViewTests(TestCase):
    def setUp(self):
        self.login_url = reverse('authentication:login')
        self.staff_user = User.objects.create_user(
            username='staff', password='StrongPass123!', is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username='regular', password='StrongPass123!', is_staff=False,
        )

    def test_login_page_loads(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    def test_staff_user_can_log_in(self):
        response = self.client.post(self.login_url, {
            'username': 'staff',
            'password': 'StrongPass123!',
        })
        # LoginView redirige (302) en éxito
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_non_staff_user_is_rejected(self):
        response = self.client.post(self.login_url, {
            'username': 'regular',
            'password': 'StrongPass123!',
        })
        # Credenciales correctas pero sin is_staff: el form debe rechazar
        # y el usuario NO queda autenticado en la sesión.
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertFormError(
            response.context['form'], None,
            'This account does not have access to the admin panel.',
        )

    def test_wrong_password_is_rejected(self):
        response = self.client.post(self.login_url, {
            'username': 'staff',
            'password': 'wrong-password',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_redirects(self):
        self.client.login(username='staff', password='StrongPass123!')
        response = self.client.post(reverse('authentication:logout'))
        self.assertEqual(response.status_code, 302)
