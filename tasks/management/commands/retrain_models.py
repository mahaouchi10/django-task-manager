from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from tasks.ml import _model_path, predict_duration, train_best_model

User = get_user_model()


class Command(BaseCommand):
    help = "Retrain the task-duration prediction model(s)."

    def add_arguments(self, parser):
        parser.add_argument('--user', type=int, default=None,
                            help='Retrain only for the given user id. If omitted, retrain for every user.')

    def handle(self, *args, **options):
        user_id = options.get('user')
        if user_id is not None:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                self.stderr.write(f"Utilisateur {user_id} introuvable.")
                return
            self._retrain(user)
            return

        users_with_models = set()
        for user in User.objects.all():
            users_with_models.add(user)

        for user in users_with_models:
            self._retrain(user)

        total = len(users_with_models)
        self.stdout.write(self.style.SUCCESS(f"{total} utilisateur(s) traité(s)."))

    def _retrain(self, user):
        bundle = train_best_model(user)
        if bundle is None:
            self.stdout.write(self.style.WARNING(
                f"Utilisateur {user.username} (id={user.id}) : données insuffisantes (< 5 tâches terminées), "
                f"aucun modèle enregistré."
            ))
            # Supprime un éventuel ancien modèle inutilisable.
            path = _model_path(user.id)
            if path.exists():
                path.unlink()
            return

        # If training produced a special 'constant' bundle (no informative
        # feature variation), inform the operator that a fallback heuristic
        # will be used at prediction time.
        if bundle.get('insufficient_features'):
            self.stdout.write(self.style.WARNING(
                f"Utilisateur {user.username} (id={user.id}) : features constantes détectées, "
                f"aucun modèle entraîné — heuristique basée sur la complexité moyenne sera utilisée. "
                f"(mean_complexity={bundle.get('mean_complexity')}, mean_duration={bundle.get('mean_duration')}, n={bundle.get('samples')})"
            ))
            return

        # Normal trained model
        self.stdout.write(self.style.SUCCESS(
            f"Utilisateur {user.username} (id={user.id}) : modèle entraîné et sauvegardé "
            f"({bundle['label']}, R²={bundle['r2']}, RMSE={bundle['rmse']}, n={bundle['samples']})."
        ))
