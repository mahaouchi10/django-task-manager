import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taskmanager.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth.models import User

c = Client()
c.force_login(User.objects.get(username='admin'))
r = c.get('/tasks/stats/')
body = r.content.decode('utf-8', 'replace')

# Show the chart-body context
idx = body.find('class="chart-body"')
print('--- chart-body snippet ---')
print(body[idx-10:idx+300])

# Show first plotly div and its parent container styles
import re
# find the outer div that wraps plotly-graph-div
outer = re.findall(r'<div style="[^"]*">.*?<div id="[^"]*" class="plotly-graph-div"[^>]*>', body, re.DOTALL)
print('\n--- outer wrappers ---')
for o in outer[:2]:
    print(o[:300])
