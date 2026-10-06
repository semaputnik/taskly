# Taskly - Deployment

Deploy the project to [FastAPI Cloud](https://fastapicloud.com) with the included GitHub Actions workflow.

## Create the FastAPI Cloud Application

Create an application in FastAPI Cloud and set its [Application Directory](https://fastapicloud.com/docs/builds-and-deployments/application-directory/) to `backend`.

Connect a PostgreSQL database using the [Neon](https://fastapicloud.com/docs/integrations/neon-integration/) or [Supabase](https://fastapicloud.com/docs/integrations/supabase-integration/) integration. Both integrations configure a `DATABASE_URL` secret automatically. You can also configure `DATABASE_URL` manually for another PostgreSQL provider.

## Configure the Application

### Environment Variables

Add these required [environment variables](https://fastapicloud.com/docs/builds-and-deployments/environment-variables/) to the FastAPI Cloud application:

* `PROJECT_NAME`: The name of the project, used in the API documentation and emails.
* `FIRST_SUPERUSER`: The email address of the first superuser. Whoever registers it while there is no superuser becomes one.
* `FRONTEND_HOST`: The public URL of the application, such as the generated `https://your-app.fastapicloud.dev` URL or a custom domain. Passkeys are bound to its hostname: changing it later makes every passkey unusable (see [Passkeys and the Hostname](deployment-docker-compose.md#passkeys-and-the-hostname)).

To let webhooks point at loopback and private addresses, set `OUTBOUND_ALLOW_PRIVATE_ADDRESSES` to `true`. It is off by default (see [Webhooks](deployment-docker-compose.md#webhooks)).

To enable emails, add these optional environment variables with values from your email provider:

* `SMTP_HOST`
* `SMTP_USER`
* `EMAILS_FROM_EMAIL`

To enable Sentry, configure `SENTRY_DSN`.

### Secrets

Add these required values and mark them as secrets:

* `SECRET_KEY`: A secret key used to sign security tokens.
* `WEBHOOK_SECRET_KEY`: A separate secret key that encrypts bot users' webhook secrets. Set it once and keep it: changing it makes every owner regenerate their webhook secrets (see [Webhooks](deployment-docker-compose.md#webhooks)). Rotating `SECRET_KEY` does not affect them.
* `DATABASE_URL`: The PostgreSQL connection URL, configured automatically when using a database integration.

To enable emails with an authenticated provider, add `SMTP_PASSWORD` as a secret.

You can generate a secure value for `SECRET_KEY` and for `WEBHOOK_SECRET_KEY` (use a different value for each) with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Configure Continuous Deployment

The included `.github/workflows/deploy.yml` workflow builds the frontend, prepares the database, and deploys the application. It currently runs only manually from the **Actions** tab; once the secrets below are configured, restore the `push` trigger in the workflow to deploy on every push to `master`.

Log in to FastAPI Cloud and configure the [deploy token](https://fastapicloud.com/docs/advanced-features/deploy-tokens/) and application ID as GitHub repository secrets:

```bash
uv run fastapi login
uv run fastapi cloud setup-ci --secrets-only --app-id <your-app-id>
```

If the GitHub CLI is installed and authenticated, the command configures `FASTAPI_CLOUD_TOKEN` and `FASTAPI_CLOUD_APP_ID` automatically. Otherwise, it prints the values so you can add them in your repository under **Settings** > **Secrets and variables** > **Actions**.

The workflow runs database migrations before deploying. In the repository's **Settings** > **Secrets and variables** > **Actions** page, add these repository variables:

* `PROJECT_NAME`
* `FIRST_SUPERUSER`

Add these repository secrets:

* `DATABASE_URL`
* `SECRET_KEY`
* `WEBHOOK_SECRET_KEY`

Use the same values configured in FastAPI Cloud. For `DATABASE_URL`, use the connection URL from your database provider. The database must be reachable from GitHub-hosted runners so the preparation step can connect to it.

The deployment workflow performs these steps:

1. Installs and builds the frontend into `backend/app/frontend`.
2. Runs `backend/scripts/prestart.sh` to apply database migrations.
3. Deploys the project with `uv run fastapi deploy`.

## The First Superuser and Recovery

Nothing is seeded: register `FIRST_SUPERUSER` at `/signup` to become the superuser. For the superuser's recovery code, and for moving an installation that used passwords over to passkeys, see [Passkeys and the Hostname](deployment-docker-compose.md#passkeys-and-the-hostname); run `python -m app.superuser_recovery_code` wherever the backend runs with the application's settings.

## URLs

Replace `your-app.fastapicloud.dev` with the URL of your FastAPI Cloud application.

Application (frontend and API): `https://your-app.fastapicloud.dev`

Interactive API docs: `https://your-app.fastapicloud.dev/docs`

## Docker Compose

For deployment to your own server, see the [Docker Compose deployment guide](./deployment-docker-compose.md).

## Pre-commit Auto-fixes

Install the [PR Push](https://github.com/apps/pr-push) GitHub App to let the pre-commit workflow push automated fixes to pull request branches.
