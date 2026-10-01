# ShopVerse

## Deploy on PythonAnywhere

PythonAnywhere currently supports Python 3.13 on its `innit` system image. This
project uses Django 6.1, so choose Python 3.13 when creating the virtualenv and
the web app. If your account uses an older system image, switch it to `innit`
first.

1. In a PythonAnywhere Bash console, clone the public repository and install
   the dependencies:

   ```bash
   git clone https://github.com/amankumarktr9080-spec/ecommerce.git
   cd ~/ecommerce/backend
   mkvirtualenv ecommerce-venv --python=/usr/bin/python3.13
   pip install -r requirements.txt
   ```

2. In the PythonAnywhere Files tab, create `~/ecommerce/backend/.env` with
   production-only settings. Replace `<username>` with your PythonAnywhere
   username and generate a new, private `SECRET_KEY`:

   ```dotenv
   SECRET_KEY=<new-random-secret>
   DEBUG=false
   ALLOWED_HOSTS=<username>.pythonanywhere.com
   CSRF_TRUSTED_ORIGINS=https://<username>.pythonanywhere.com
   SQLITE_PATH=/home/<username>/ecommerce/backend/db.sqlite3
   MEDIA_ROOT=/home/<username>/ecommerce/backend/media
   ```

   Add optional payment, Google OAuth, or SMTP settings only if those features
   are configured for the deployed domain. Do not copy local credentials into
   Git or commit this `.env` file.

3. In the Web tab, create a **Manual configuration** web app using Python 3.13.
   Set its virtualenv to `/home/<username>/.virtualenvs/ecommerce-venv`.
   Set the source code and working directory to
   `/home/<username>/ecommerce/backend`.

4. Open the WSGI configuration file linked from the Web tab, replace its
   contents with the following, and replace `<username>`:

   ```python
   import os
   import sys

   project_path = "/home/<username>/ecommerce/backend"
   if project_path not in sys.path:
       sys.path.insert(0, project_path)

   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings")

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

5. In a Bash console, run migrations and collect static files:

   ```bash
   cd ~/ecommerce/backend
   workon ecommerce-venv
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```

   Run `python manage.py createsuperuser` if you need a new site administrator.

6. In the Web tab, add a static-files mapping from `/static/` to
   `/home/<username>/ecommerce/backend/staticfiles/`. If the app serves uploaded
   media, also map `/media/` to
   `/home/<username>/ecommerce/backend/media/`. Reload the web app.

### Database and existing records

The SQLite database and uploaded media are intentionally excluded from Git.
Deploying this repository creates a new SQLite database when migrations run;
it does not include the local users, orders, or other existing records. Do not
upload a database containing customer or account data to a public repository.
