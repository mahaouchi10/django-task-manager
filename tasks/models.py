from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Task(models.Model):
    class Category(models.TextChoices):
        WORK = 'travail', 'Travail'
        STUDY = 'etudes', 'Études'
        PERSONAL = 'perso', 'Personnel'

    class Priority(models.TextChoices):
        LOW = 'basse', 'Basse'
        MEDIUM = 'moyenne', 'Moyenne'
        HIGH = 'haute', 'Haute'

    class Status(models.TextChoices):
        TODO = 'a_faire', 'À faire'
        IN_PROGRESS = 'en_cours', 'En cours'
        DONE = 'terminee', 'Terminée'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='Utilisateur',
    )
    title = models.CharField('Titre', max_length=200)
    description = models.TextField('Description', blank=True)
    category = models.CharField(
        'Catégorie', max_length=20, choices=Category.choices,
        default=Category.PERSONAL,
    )
    priority = models.CharField(
        'Priorité', max_length=20, choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    complexity = models.PositiveSmallIntegerField(
        'Complexité (1 à 5)', default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Estimation de la complexité de 1 (simple) à 5 (très complexe)',
    )
    status = models.CharField(
        'Statut', max_length=20, choices=Status.choices,
        default=Status.TODO,
    )
    created_at = models.DateTimeField('Date de création', auto_now_add=True)
    completed_at = models.DateTimeField(
        'Date de fin réelle', null=True, blank=True,
        help_text='Renseignée automatiquement quand la tâche est terminée',
    )

    class Meta:
        verbose_name = 'Tâche'
        verbose_name_plural = 'Tâches'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def duration_days(self):
        if self.completed_at and self.created_at:
            return (self.completed_at - self.created_at).total_seconds() / 86400.0
        return None

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE and self.completed_at is None:
            self.completed_at = timezone.now()
        elif self.status != self.Status.DONE:
            self.completed_at = None
        return super().save(*args, **kwargs)