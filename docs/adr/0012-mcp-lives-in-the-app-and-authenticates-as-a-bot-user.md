# MCP lives in this app, and authenticates as a bot user

An agent working a user's tasks today means someone writes an HTTP client for
the REST API by hand and teaches the model the task schema and every rule
around it by hand too (spec #247's problem statement). MCP gives the model a
small set of tools shaped around what someone actually asks for, rather than
around routes — but only if it is cheap enough to stand up that an existing
installation actually turns it on, and only if what it is allowed to reach is
exactly as narrow as the product already makes a bot user's reach.

Two decisions follow from that, both settled in spec #247 and acted on for
the first time here, by #252.

## Decision

**The MCP server is this app, not a second one.** `/mcp` is an ASGI route
mounted outside the versioned REST prefix (`app.mcp`, wired into
`app.main`'s own `FastAPI` instance and its own lifespan). Deployment stays
one container either way (`docs/deployment-docker-compose.md`); there is one
place access rules live (`app.api.access`), not two to keep in step; and a
tool handler calls this application's own task, access and read-model layers
directly, in the same process, rather than making an HTTP call back into the
process it already runs in.

**The credential is a bot user's token — nothing else.** `/mcp` resolves the
caller through `app.api.deps.get_mcp_caller`, built on the same
`_authenticate_bot` the REST API's `get_caller` (spec #245) already uses: an
unknown, revoked, expired or deleted bot user's token is refused exactly as
it is everywhere else, and the scope, the grants and the activity-log
attribution a tool call acts under are the ones the product already has, not
a second description of them. There is no OAuth authorization-server flow —
no `/authorize`, no dynamic client registration, no token endpoint of this
server's own. The MCP Python SDK's own bearer-token verification (a
`TokenVerifier`) was deliberately not used either, even though it exists for
exactly this shape of credential: wiring it on requires `AuthSettings` with a
mandatory `issuer_url` and advertises OAuth protected-resource metadata
(`/.well-known/oauth-protected-resource`) once `resource_server_url` is set —
machinery for a flow this product does not have and does not want an agent's
client guessing it might. A plain ASGI gateway in front of the mounted route
(`app.mcp._BotGateway`) reads the `Authorization` header itself instead.

A human session reaching `/mcp` is refused for what it is — `bot_only`, the
mirror of `human_only` at the REST API's own human-only endpoints — never for
a permission a scope could have granted: there is no MCP tool built to serve
a human caller at all.

## Consequences

**Nothing about the caller is cached.** `get_mcp_caller` is called once by
the gateway, to decide whether a request is let through at all, and again
inside every tool, each on its own database session: a scope edited between
two calls shows in the second, the same promise `GET /caller` already makes.
The gateway's check and the tool's are not threaded together on purpose —
"nothing cached" taken to its conclusion is that a tool call stands on its
own exactly as if it had been dispatched without a gateway in front of it,
which is also what keeps a tool testable and callable as a single, complete
unit.

**A protocol session is bound to the token that opened it.** The Streamable
HTTP transport keeps a session id across calls; `_BotGateway` remembers,
for the life of this process, which token's hash opened each one, and
refuses a session id presented with a different token rather than serving
it. One mounted server still serves any number of agents at once, because
every tool call's caller comes from that call's own token, not from
anything the server was configured with (spec #247's closing note) — the
session binding only stops one agent's open session from being continued as
another's.

**One bot user per agent is the deployment's convention, not a server
rule.** Nothing here enforces it — a scope and a token already belong to one
bot user, and two agents sharing one would simply be impossible to tell
apart in the log or revoke apart, the same cost sharing a REST token already
has (`CONTEXT.md`, "Bot user"). `docs/deployment-docker-compose.md`
documents it as the way to connect an agent.
