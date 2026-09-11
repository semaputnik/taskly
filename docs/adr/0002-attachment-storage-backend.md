# Attachment storage is a swappable backend, defaulting to internal

We considered making Paperless-ngx the storage for task attachments outright,
but that would force every user to connect an external instance before they
could attach a file at all, and lock the architecture to one integration
before it's needed.

We decided attachments stay stored internally by Taskly by default, behind a
storage abstraction. This keeps attachments working out of the box while
leaving room to add Paperless-ngx (or another backend) later as an optional,
per-user choice (see Future ideas in `docs/features.md`) without reworking
how attachments are modeled or exposed through the API.
