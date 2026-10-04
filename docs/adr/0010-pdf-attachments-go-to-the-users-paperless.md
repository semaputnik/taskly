# PDF attachments go to the user's Paperless, which Taskly never deletes from

ADR-0002 kept attachments internal and left room for a per-user external
store. The store is Paperless-ngx, the document archive the kind of person who
self-hosts a task tracker tends to run beside it, and it takes PDFs only: a
PDF is a document an archive wants, and a screenshot or a spreadsheet is not.
A user connects their own instance in Settings; nothing changes for anyone who
does not.

**The one place, not a mirror.** Taskly could have kept a copy and sent
Paperless a second. It does not: a PDF a connected user attaches is kept in
Paperless and nowhere else, and Taskly holds the document's id and serves the
bytes from there. A mirror doubles the space and asks which copy is real; the
point of the connection is that the archive is the one place documents live.
The cost is accepted plainly: while Paperless is unreachable, those files are.

**Handed over in the background.** Paperless consumes a document
asynchronously, so for a minute or so after upload there is no document to
point at. Taskly keeps the bytes itself for that minute, answers the upload at
once, sends the file and polls for the result from the background loop the
webhooks brought, and drops its copy only once Paperless has confirmed. If
Paperless is down or refuses the file, the attempt is retried on the same
schedule as a webhook delivery and then the file simply stays in Taskly, with
the reason shown and an action to try again. An attachment is therefore
always downloadable, and never in a state the owner has to wait out.

**A duplicate is linked, not refused.** Paperless rejects a file it already
holds. Rather than refuse the attachment or keep a local copy of a document
the archive already has, Taskly links the attachment to the existing
document, which it finds by checksum before sending. So one Paperless
document may stand behind several attachments, which is harmless only
because of the next point.

**Taskly never deletes from Paperless.** Removing an attachment kept in
Paperless drops the link and nothing else, and deleting a Taskly account
touches nothing there. The document was handed to the user's archive, which
has since OCR'd and filed it; Taskly is not its owner and a slip in a task
should not reach into the archive. This also keeps shared documents (above)
safe without reference counting.

**What Paperless learns.** The file under its original name, a `Taskly` tag
made on first use, and a note on the document naming the task and linking
back to it — one note per task the document is attached to. Tags and notes
are ordinary Paperless API; custom fields would have needed setup on the
Paperless side first.

**The original, not the archive copy.** A download returns the bytes that
were attached, not Paperless's OCR'd PDF/A: an attachment is what was
attached, and a bot comparing checksums must not be surprised. The OCR
version is one click away in Paperless itself.

**One switch for every outbound address.** A Paperless address is a URL a
user typed that the server will connect to, the same shape of risk as a
webhook URL, so it is refused on loopback and private ranges under the same
installation setting (ADR-0009) and allowed by the same flip.

**Nothing moves on connecting.** A user who connects Paperless with a hundred
local PDFs keeps them local; only new PDFs go. Moving an archive without being
asked is what ADR-0002 declined to do, and a "send existing PDFs" action is
recorded as a future idea instead.
