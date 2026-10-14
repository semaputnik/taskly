"""
`app/crud.py` as a package: one module per cluster of aggregates, plus a
module of predicates shared across more than one of them.

This package holds no re-export surface of its own — `app/crud.py` is that
surface, importing every name the 35 call sites outside this package use, so
the split is invisible to them. Code inside this package reaches across its
own modules by importing their public names, same as any other caller; a
private helper never crosses a module boundary, which is what `predicates.py`
is for.

**`commit: bool = True`, where a function offers it, is the seam a write path
moves through on its way to becoming an operation (ADR-0013).** By default a
function here lands its own write the moment it returns, same as every
caller outside this package already relies on. `commit=False` is for the one
other kind of caller: an operation (`app.tasks`, `app.comments`) that opened
a `UnitOfWork` of its own and needs this write to land as part of that body
rather than as a transaction by itself. The operation is always the only
caller that passes it — a route, a test, or another function in this package
never does, because the operation is the only thing in this codebase that
owns a transaction wider than one write. `commit=False` never means "do not
commit at all": the function still flushes what it staged, so a caller that
reads the row back (`session.refresh`) finds it exactly as committed:
it means "the caller's `UnitOfWork` will, once its own body is done."

A write path growing an operation of its own goes through both changes in
the same commit: the function it drives gains `commit: bool = True` if it
does not already have one shaped like it, and the operation becomes the one
caller passing `commit=False`. `create_task` and `update_task` (`tasks.py`),
`create_comment` (`comments.py`) and `create_user` (`users.py`) — plus
`app.deletions.delete_task`, outside this package — are the seam today: 4 of
this package's 23 commit sites (ADR-0013). The other 19 still commit
unconditionally, each its own transaction, until a write path of theirs
grows an operation to own it.
"""
