from time import time

from django.core.management.base import BaseCommand

from users.login_protection import WINDOW_SECONDS
from users.models import LoginAttemptBudget


class Command(BaseCommand):
    help = "Elimina contadores de login cuya última ventana tiene más de un día."

    def handle(self, *args, **options):
        oldest_window = (int(time()) - 86400) // WINDOW_SECONDS
        count, _ = LoginAttemptBudget.objects.filter(window__lt=oldest_window).delete()
        self.stdout.write(f"Contadores eliminados: {count}")
