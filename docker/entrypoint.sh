#!/bin/sh
set -e

# Wait for Postgres to become available
if [ -n "$POSTGRES_HOST" ]; then
  until pg_isready -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" >/dev/null 2>&1; do
    echo "Waiting for Postgres..."
    sleep 1
  done
fi


# Create migrations (if any) and run migrations, then collect static files
python manage.py makemigrations asn --noinput || true
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Create a superuser if environment variables are provided and user doesn't exist
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Creating superuser $DJANGO_SUPERUSER_USERNAME if it does not exist..."
  python - <<'PY'
import os
import django
from django.core.exceptions import ImproperlyConfigured

os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'iranicdna_backend.settings'))
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print('Superuser created')
else:
    print('Superuser already exists')
PY
fi

exec "$@"
