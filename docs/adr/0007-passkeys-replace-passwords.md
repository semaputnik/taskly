# Passkeys replace passwords

Taskly inherited email-and-password sign-in from the template it was
bootstrapped from, with a password reset sent by e-mail. A human user now
signs in with a passkey and nothing else: there is no password to set, type,
forget or reset, and no e-mail is ever sent. Bot users are untouched; their
tokens were never passwords.

**Why not both.** The obvious step was a passkey *beside* the password: keep
registration as it was, let a user add a passkey in Settings and sign in with
it. It is the smaller change, and it is the one the reference we studied
(openGym) made by default. It was rejected because every account would keep
its weakest way in: a password can be phished, reused and guessed, and the
e-mail reset that goes with it needs an SMTP server most installations of a
personal tracker do not have. With two ways in, every rule about proving who
you are — adding a passkey, removing one, recovering an account — has to be
written twice and hold for the weaker one. With one, it is written once.

**What a passkey is here.** It is discoverable, so sign-in asks for nothing
and the browser offers the passkeys it holds for this hostname; and it
requires user verification, so as the sole credential it is still two factors
— the device and the biometric or PIN that unlocks it. It is bound to the
installation's hostname, taken from the one setting that already names it
(`FRONTEND_HOST`), rather than a second setting that could disagree with the
first.

**What replaces the reset e-mail.** A user who has lost every passkey asks the
superuser for a one-time recovery code, which they spend by creating a new
passkey. This is the superuser's first administrative function beyond listing
users, and it is deliberately not self-service: a code in an e-mail is a
password reset by another name, and an e-mail that is never used for anything
else never has to be verified. The superuser recovers themselves from the
server's command line, since there is exactly one of them and nobody above
them.

**What this costs.** A browser without passkey support has no way in at all;
there is no guest mode and no fallback. An installation that changes its
hostname invalidates every passkey it has issued. Existing accounts made with
a password are moved over by hand: the operator issues the superuser's code
from the command line, and the superuser issues codes to everyone else. There
is no transitional release in which both ways in work, because that release
would be the "both" we chose not to build.
