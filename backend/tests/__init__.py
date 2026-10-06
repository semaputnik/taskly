import os

# The webhook delivery loop starts with the app's lifespan, which every
# `TestClient(app)` context runs. It must not run during the suite unless a
# test starts it: tests call `webhooks.deliver_due` themselves, with a mock
# transport, so nothing here ever reaches the network. This runs before
# `app.core.config` is imported, which is when settings are read.
os.environ["WEBHOOK_DELIVERY_LOOP"] = "false"
