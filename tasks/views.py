from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

import pandas as pd
import plotly.express as px

from .forms import TaskForm
from .ml import predict_duration
from .models import Task


def home(request):
    context = {}
    if request.user.is_authenticated:
        from .models import Task
        context.update({
            'total': request.user.tasks.count(),
            'done': request.user.tasks.filter(status=Task.Status.DONE).count(),
            'in_progress': request.user.tasks.filter(status=Task.Status.IN_PROGRESS).count(),
        })
    return render(request, 'home.html', context)


@login_required
def task_list(request):
    tasks = request.user.tasks.all()
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    priority_filter = request.GET.get('priority', '')
    if status_filter in dict(Task.Status.choices):
        tasks = tasks.filter(status=status_filter)
    if category_filter in dict(Task.Category.choices):
        tasks = tasks.filter(category=category_filter)
    if priority_filter in dict(Task.Priority.choices):
        tasks = tasks.filter(priority=priority_filter)

    context = {
        'tasks': tasks,
        'status_choices': Task.Status.choices,
        'current_status': status_filter,
        'category_choices': Task.Category.choices,
        'current_category': category_filter,
        'priority_choices': Task.Priority.choices,
        'current_priority': priority_filter,
        'counts': {
            'total': request.user.tasks.count(),
            'done': request.user.tasks.filter(status=Task.Status.DONE).count(),
            'todo': request.user.tasks.filter(status=Task.Status.TODO).count(),
            'in_progress': request.user.tasks.filter(status=Task.Status.IN_PROGRESS).count(),
        },
    }
    return render(request, 'tasks/task_list.html', context)


@login_required
def task_create(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, 'Tâche créée avec succès.')
            return redirect(reverse('task_list'))
    else:
        form = TaskForm()
    return render(request, 'tasks/task_form.html', {'form': form, 'title': 'Nouvelle tâche'})


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tâche mise à jour.')
            return redirect(reverse('task_list'))
    else:
        form = TaskForm(instance=task)
    return render(request, 'tasks/task_form.html', {'form': form, 'title': 'Modifier la tâche', 'task': task})


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Tâche supprimée.')
        return redirect(reverse('task_list'))
    return render(request, 'tasks/task_confirm_delete.html', {'task': task})


@login_required
def predict_api(request):
    category = request.GET.get('category', Task.Category.PERSONAL)
    priority = request.GET.get('priority', Task.Priority.MEDIUM)
    try:
        complexity = int(request.GET.get('complexity', 1))
    except (TypeError, ValueError):
        complexity = 1
    complexity = max(1, min(5, complexity))

    if category not in dict(Task.Category.choices):
        category = Task.Category.PERSONAL
    if priority not in dict(Task.Priority.choices):
        priority = Task.Priority.MEDIUM

    result = predict_duration(request.user, category, priority, complexity)
    return JsonResponse(result)


@login_required
def stats(request):
    qs = request.user.tasks.all()
    df = pd.DataFrame(
        list(qs.values(
            'status', 'category', 'priority', 'complexity', 'created_at', 'completed_at'
        ))
    )

    context = {
        'charts': [],
        'total': qs.count(),
        'done_count': qs.filter(status=Task.Status.DONE).count(),
        'in_progress': qs.filter(status=Task.Status.IN_PROGRESS).count(),
        'todo': qs.filter(status=Task.Status.TODO).count(),
        'avg_duration_days': None,
        'summary': None,
    }

    # Aucune tâche : on rend la page avec des zéros et le message vide du template.
    if df.empty:
        return render(request, 'tasks/stats.html', context)

    df['created_at'] = pd.to_datetime(df['created_at'])
    df['completed_at'] = pd.to_datetime(df['completed_at'])

    choices_map = {
        'category': dict(Task.Category.choices),
        'priority': dict(Task.Priority.choices),
        'status': dict(Task.Status.choices),
    }

    def top(series):
        counts = series.value_counts()
        if counts.empty:
            return None
        key = counts.idxmax()
        name = series.name
        return {
            'key': key,
            'label': choices_map.get(name, {}).get(key, key),
            'count': int(counts.iloc[0]),
        }

    context['summary'] = {
        'category': top(df['category']),
        'priority': top(df['priority']),
        'status': top(df['status']),
    }

    def add_chart(title, fig, height='320px'):
        context['charts'].append({
            'title': title,
            'html': fig.to_html(
                full_html=False, include_plotlyjs=False,
                default_height=height, default_width='100%',
            ).replace('height:100%;', 'height:' + height + ';'),
        })

    def add_message(title, message):
        context['charts'].append({
            'title': title,
            'html': '<div style="padding:18px 14px;color:#64748b;text-align:center;">'
                    + message + '</div>',
        })

    # --- Graphique 1 : Nombre de tâches par statut ---
    by_status = df['status'].value_counts().reset_index()
    by_status.columns = ['status', 'count']
    by_status['label'] = by_status['status'].map(dict(Task.Status.choices))
    by_status = by_status.sort_values('count', ascending=False)
    fig_status = px.bar(
        by_status, x='label', y='count',
        title='Nombre de tâches par statut',
        text='count',
        labels={'label': 'Statut', 'count': 'Nombre'},
    )
    fig_status.update_traces(textposition='outside', textfont_size=13)
    fig_status.update_layout(
        font=dict(size=13), margin=dict(t=40, b=70),
        yaxis=dict(tickfont_size=12), xaxis=dict(tickfont_size=12),
    )
    add_chart('Nombre de tâches par statut', fig_status, height='380px')

    # --- Graphique 2 : Répartition des tâches par catégorie (camembert) ---
    by_category = df['category'].value_counts().reset_index()
    by_category.columns = ['category', 'count']
    by_category['label'] = by_category['category'].map(dict(Task.Category.choices))
    fig_cat = px.pie(
        by_category, names='label', values='count',
        title='Répartition des tâches par catégorie',
    )
    fig_cat.update_traces(
        textposition='inside',
        textinfo='label+percent',
        textfont_size=14,
        hovertemplate='%{label}: %{value} (%{percent})<extra></extra>',
    )
    fig_cat.update_layout(
        font=dict(size=13),
        legend=dict(
            font=dict(size=13),
            orientation='h',
            yanchor='bottom',
            y=-0.22,
            xanchor='center',
            x=0.5,
        ),
        margin=dict(t=40, b=50),
    )
    add_chart('Répartition des tâches par catégorie', fig_cat, height='380px')

    # --- Graphique 3 : Nombre de tâches par priorité (barres) ---
    priority_counts = df['priority'].value_counts()
    by_priority = pd.DataFrame({
        'label': [dict(Task.Priority.choices).get(k, k) for k, _ in Task.Priority.choices],
        'count': [int(priority_counts.get(k, 0)) for k, _ in Task.Priority.choices],
    })
    fig_prio = px.bar(
        by_priority, x='label', y='count',
        title='Nombre de tâches par priorité',
        text='count',
        labels={'label': 'Priorité', 'count': 'Nombre'},
    )
    fig_prio.update_traces(textposition='outside', textfont_size=13)
    fig_prio.update_layout(
        font=dict(size=13), margin=dict(t=40, b=70),
        yaxis=dict(tickfont_size=12, dtick=1), xaxis=dict(tickfont_size=12),
    )
    add_chart('Nombre de tâches par priorité', fig_prio, height='380px')

    # --- Graphique 4 : Durée moyenne d'achèvement par catégorie (tâches terminées) ---
    done = df[df['status'] == Task.Status.DONE].copy()
    has_real_duration = False
    if not done.empty and done['completed_at'].notna().any():
        done['duration_days'] = (done['completed_at'] - done['created_at']).dt.total_seconds() / 86400.0
        done = done.dropna(subset=['duration_days'])
        if not done.empty:
            has_real_duration = True
            context['avg_duration_days'] = round(float(done['duration_days'].mean()), 2)
            avg_by_type = done.groupby('category', as_index=False)['duration_days'].mean()
            avg_by_type['label'] = avg_by_type['category'].map(dict(Task.Category.choices))
            fig_avg = px.bar(
                avg_by_type, x='label', y='duration_days',
                text='duration_days',
                title="Durée moyenne d'achèvement par catégorie",
                labels={'label': 'Catégorie', 'duration_days': 'Durée moyenne (jours)'},
            )
            fig_avg.update_traces(texttemplate='%{text:.1f}', textposition='outside', textfont_size=13)
            fig_avg.update_layout(
                font=dict(size=13), margin=dict(t=40, b=70),
                yaxis=dict(tickfont_size=12), xaxis=dict(tickfont_size=12),
            )
            add_chart("Durée moyenne d'achèvement par catégorie", fig_avg, height='380px')

    if not has_real_duration:
        add_message(
            "Durée moyenne d'achèvement par catégorie",
            "Aucune donnée disponible pour calculer la durée moyenne. "
            "Terminez des tâches avec une date de fin réelle pour obtenir cette statistique.",
        )

    # --- Graphique 5 : Évolution des tâches créées dans le temps (cumul) ---
    evolution = df.sort_values('created_at').copy()
    evolution['cumul'] = range(1, len(evolution) + 1)
    fig_evol = px.line(
        evolution, x='created_at', y='cumul',
        title='Évolution des tâches créées dans le temps',
        labels={'created_at': 'Date', 'cumul': 'Nombre cumulé'},
        markers=True,
    )
    fig_evol.update_traces(textfont_size=13, line=dict(width=3), marker=dict(size=6))
    fig_evol.update_layout(font=dict(size=13), margin=dict(t=40, b=60))
    add_chart('Évolution des tâches créées dans le temps', fig_evol, height='380px')

    return render(request, 'tasks/stats.html', context)

