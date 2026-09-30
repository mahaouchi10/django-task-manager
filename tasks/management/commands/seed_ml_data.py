from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tasks.models import Task

SEED_TASKS = [
    # (titre, catégorie, priorité, complexité, date création, date fin, durée attendue en jours)
    ("Corriger un bug simple", Task.Category.WORK, Task.Priority.LOW, 1, date(2026, 8, 1), date(2026, 8, 2), 1),
    ("Lire un chapitre de Java", Task.Category.STUDY, Task.Priority.LOW, 1, date(2026, 8, 3), date(2026, 8, 4), 1),
    ("Organiser les fichiers personnels", Task.Category.PERSONAL, Task.Priority.LOW, 1, date(2026, 8, 5), date(2026, 8, 7), 2),
    ("Préparer un rapport simple", Task.Category.STUDY, Task.Priority.MEDIUM, 2, date(2026, 8, 8), date(2026, 8, 10), 2),
    ("Ajouter une fonctionnalité simple", Task.Category.WORK, Task.Priority.MEDIUM, 2, date(2026, 8, 11), date(2026, 8, 14), 3),
    ("Planifier les tâches de la semaine", Task.Category.PERSONAL, Task.Priority.MEDIUM, 2, date(2026, 8, 15), date(2026, 8, 16), 1),
    ("Réviser un module Java", Task.Category.STUDY, Task.Priority.HIGH, 2, date(2026, 8, 17), date(2026, 8, 20), 3),
    ("Corriger plusieurs bugs", Task.Category.WORK, Task.Priority.HIGH, 2, date(2026, 8, 21), date(2026, 8, 24), 3),
    ("Préparer une présentation", Task.Category.STUDY, Task.Priority.HIGH, 3, date(2026, 8, 25), date(2026, 8, 29), 4),
    ("Développer une page web", Task.Category.WORK, Task.Priority.MEDIUM, 3, date(2026, 8, 1), date(2026, 8, 5), 4),
    ("Créer une interface utilisateur", Task.Category.WORK, Task.Priority.LOW, 3, date(2026, 8, 6), date(2026, 8, 11), 5),
    ("Organiser un événement personnel", Task.Category.PERSONAL, Task.Priority.HIGH, 3, date(2026, 8, 12), date(2026, 8, 16), 4),
    ("Développer une API Django", Task.Category.WORK, Task.Priority.HIGH, 4, date(2026, 8, 17), date(2026, 8, 22), 5),
    ("Concevoir une base de données", Task.Category.WORK, Task.Priority.MEDIUM, 4, date(2026, 8, 23), date(2026, 8, 29), 6),
    ("Réaliser un projet universitaire", Task.Category.STUDY, Task.Priority.HIGH, 4, date(2026, 8, 1), date(2026, 8, 7), 6),
    ("Développer un système d'authentification", Task.Category.WORK, Task.Priority.HIGH, 4, date(2026, 8, 8), date(2026, 8, 15), 7),
    ("Développer un module complet", Task.Category.WORK, Task.Priority.MEDIUM, 5, date(2026, 8, 16), date(2026, 8, 24), 8),
    ("Réaliser une analyse de données", Task.Category.STUDY, Task.Priority.HIGH, 5, date(2026, 8, 25), date(2026, 9, 2), 8),
    ("Développer une application web", Task.Category.WORK, Task.Priority.HIGH, 5, date(2026, 8, 3), date(2026, 8, 12), 9),
    ("Concevoir un système intelligent", Task.Category.WORK, Task.Priority.HIGH, 5, date(2026, 8, 13), date(2026, 8, 24), 11),
]


def _to_aware(value):
    # Midday keeps an exact whole number of days in duration_days().
    naive = datetime.combine(value, time(12, 0, 0))
    return timezone.make_aware(naive, timezone.get_current_timezone())


class Command(BaseCommand):
    help = (
        "Peuple la base avec 20 tâches de test DONE pour l'utilisateur 'admin' "
        "et vérifie que duration_days() produit les durées attendues."
    )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username='admin')
        except User.DoesNotExist:
            raise CommandError(
                "Utilisateur 'admin' introuvable. Créez-le avant de lancer cette commande."
            )

        with transaction.atomic():
            deleted_count = Task.objects.filter(user=user).delete()[0]

            created_ids = []
            for title, category, priority, complexity, created_on, completed_on, _ in SEED_TASKS:
                task = Task(
                    user=user,
                    title=title,
                    category=category,
                    priority=priority,
                    complexity=complexity,
                    status=Task.Status.DONE,
                    completed_at=_to_aware(completed_on),
                )
                task.save()
                # auto_now_add overwrites created_at on insert, so set it directly.
                Task.objects.filter(pk=task.pk).update(created_at=_to_aware(created_on))
                created_ids.append(task.pk)

            self.stdout.write(self.style.SUCCESS(
                f"Anciennes tâches supprimées : {deleted_count} (utilisateur {user.username})"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"Tâches créées : {len(created_ids)} (utilisateur {user.username})"
            ))

            failures = []
            tasks = list(Task.objects.filter(user=user).order_by('created_at'))
            for task in tasks:
                expected = next(item[6] for item in SEED_TASKS if item[0] == task.title)
                actual = task.duration_days()
                status_line = "OK" if actual == expected else "ÉCHEC"
                self.stdout.write(
                    f"  {task.title!r:45} catégorie={task.category:8} priorité={task.priority:7} "
                    f"complexité={task.complexity} durée={actual} attendue={expected} -> {status_line}"
                )
                if actual != expected:
                    failures.append((task.title, actual, expected))

            wrong_status = Task.objects.filter(user=user).exclude(status=Task.Status.DONE).count()
            count = Task.objects.filter(user=user).count()

            if len(tasks) != 20:
                self.stdout.write(self.style.ERROR(
                    f"Échec : {len(tasks)} tâches pour {user.username} au lieu de 20."
                ))
            if wrong_status:
                self.stdout.write(self.style.ERROR(
                    f"Échec : {wrong_status} tâche(s) non DONE."
                ))
            if failures:
                self.stdout.write(self.style.ERROR(f"Échec : {len(failures)} durée(s) incorrecte(s)."))
                # Quitter depuis la transaction force un rollback complet
                # (anciennes tâches conservées, aucune nouvelle insérée).
                self.exit(1)

        self.stdout.write(self.style.SUCCESS(
            f"Validation OK : {count} tâches DONE, toutes chez {user.username}, "
            f"durées conformes aux valeurs attendues."
        ))