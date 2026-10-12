"""
Tags: the vocabulary itself (creating, renaming, deleting, merging, finding
near-duplicates) and the tag names on a task, which the task write path reads
and replaces as part of creating or updating a task.
"""

import hashlib
import re
import uuid
from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, col, func, select

from app.models import (
    ActivityAction,
    ActivityEntityType,
    ActivityEntry,
    Tag,
    TagDuplicateDismissal,
    TagPublic,
    Task,
    TaskTag,
)

from .bot_users import get_bot_user_refs
from .predicates import archived_task_ids, not_deleted


def get_tags(
    *,
    session: Session,
    owner_id: uuid.UUID,
    q: str | None = None,
    contains: str | None = None,
    near: str | None = None,
    skip: int = 0,
    limit: int = 100,
    name_creators: bool = True,
) -> tuple[list[TagPublic], int]:
    """
    The user's tags, each with the number of tasks carrying it. `q` matches
    from the start of the name, ignoring case, so what they type narrows to
    what they typed before rather than to every tag with those letters
    somewhere inside — the autocomplete-while-typing read. `contains` matches
    anywhere in the name instead, ignoring case, the way `search_tasks`'s own
    `query` matches a title: a caller who does not know how a tag starts
    (`list_tags`, spec #254) still finds it. `near` finds the tags a name
    would read the same as (`tag_key`), over the whole vocabulary: what a
    name about to become a new tag would duplicate (FR-01.28).
    """
    where: list[Any] = [Tag.owner_id == owner_id]
    if q:
        where.append(col(Tag.name).ilike(f"{q}%"))
    if contains:
        where.append(col(Tag.name).icontains(contains, autoescape=True))
    if near is not None:
        # Narrowed in the database to names that fold to the key with or
        # without a trailing "s", then held to `tag_key` exactly: this runs as
        # a name is typed, so it must not read the whole vocabulary each time.
        key = _tag_key(near)
        folded = func.lower(
            func.regexp_replace(func.trim(col(Tag.name)), r"[\s_-]+", " ", "g")
        )
        candidates = session.exec(
            select(Tag.name).where(
                Tag.owner_id == owner_id, folded.in_([key, f"{key}s"])
            )
        ).all()
        where.append(
            col(Tag.name).in_([name for name in candidates if _tag_key(name) == key])
        )

    count = session.exec(select(func.count()).select_from(Tag).where(*where)).one()
    statement = (
        select(Tag)
        .where(*where)
        # Case-insensitive, so "Reading" and "running" sit where the user looks
        # for them rather than in two alphabets.
        .order_by(func.lower(Tag.name))
        .offset(skip)
        .limit(limit)
    )
    tags = session.exec(statement).all()
    return tag_publics(session=session, tags=tags, name_creators=name_creators), count


def tag_publics(
    *, session: Session, tags: Sequence[Tag], name_creators: bool = True
) -> list[TagPublic]:
    """
    Tags as the API reports them, with how many tasks carry each.

    `task_count` is the live tasks carrying the tag — neither deleted nor
    archived with their project — because that is exactly what the task list
    filtered by the tag shows, and the count is read as a promise about that
    list (FR-01.26). The tasks archived with their project are
    reported beside it rather than dropped: deleting or merging the tag still
    reaches them, and those confirmations have to say so.

    The counts are the owner's whoever asks, a bot user included, so one tag
    never means two things (ADR-0003). Which bot user created a tag is the
    owner's to know: `name_creators` is off for a bot user reading.
    """
    if not tags:
        return []
    owner_id = tags[0].owner_id
    tag_ids = [tag.id for tag in tags]
    archived = col(Task.id).in_(archived_task_ids(owner_id))
    rows = session.exec(
        select(
            TaskTag.tag_id,
            func.count().filter(~archived),
            func.count().filter(archived),
        )
        .where(
            col(TaskTag.tag_id).in_(tag_ids),
            TaskTag.task_id == Task.id,
            not_deleted(Task),
        )
        .group_by(col(TaskTag.tag_id))
    ).all()
    counts = {tag_id: (live, archived_count) for tag_id, live, archived_count in rows}
    # Who created a tag is what its "created" entry in the activity log says.
    creators = (
        {}
        if not name_creators
        else {
            tag_id: bot_id
            for tag_id, bot_id in session.exec(
                select(ActivityEntry.entity_id, ActivityEntry.actor_bot_user_id).where(
                    ActivityEntry.entity_type == ActivityEntityType.TAG,
                    ActivityEntry.action == ActivityAction.TAG_CREATED,
                    col(ActivityEntry.entity_id).in_(tag_ids),
                )
            ).all()
            if bot_id is not None
        }
    )
    bots = get_bot_user_refs(session=session, bot_user_ids=creators.values())
    return [
        TagPublic(
            id=tag.id,
            name=tag.name,
            task_count=counts.get(tag.id, (0, 0))[0],
            archived_task_count=counts.get(tag.id, (0, 0))[1],
            created_at=tag.created_at,
            created_by_bot_user=bots.get(creators[tag.id])
            if tag.id in creators
            else None,
        )
        for tag in tags
    ]


def get_tag_by_name(*, session: Session, owner_id: uuid.UUID, name: str) -> Tag | None:
    return session.exec(
        select(Tag).where(Tag.owner_id == owner_id, Tag.name == name)
    ).first()


def get_tag_names(
    *, session: Session, owner_id: uuid.UUID, names: Sequence[str]
) -> set[str]:
    """Which of `names` the user already has a tag for."""
    if not names:
        return set()
    statement = select(Tag.name).where(
        Tag.owner_id == owner_id, col(Tag.name).in_(names)
    )
    return set(session.exec(statement).all())


def create_tag(*, session: Session, owner_id: uuid.UUID, name: str) -> Tag:
    tag = Tag(name=name, owner_id=owner_id)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def rename_tag(*, session: Session, tag: Tag, name: str) -> Tag:
    """
    Rename a tag. Tasks point at it by key, so every task carrying it shows
    the new name at once (FR-01.24).
    """
    tag.name = name
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def delete_tag(*, session: Session, tag: Tag) -> None:
    """
    Delete a tag for good (FR-01.25). The database takes it off every task
    carrying it, deleted tasks included, so a task restored later comes back
    without it.
    """
    session.delete(tag)
    session.commit()


_SEPARATORS = re.compile(r"[\s_-]+")


def _tag_key(name: str) -> str:
    """
    What a tag name reads as, for spotting likely duplicates only: letter case,
    separators (hyphens, underscores, runs of whitespace), surrounding space
    and one trailing plural "s" are set aside. Never applied to a stored name —
    names stay exactly as typed (ADR-0003).
    """
    key = _SEPARATORS.sub(" ", name).strip().lower()
    if key.endswith("s") and not key.endswith("ss") and len(key) > 3:
        key = key[:-1]
    return key


def _duplicate_signature(tags: Sequence[Tag]) -> str:
    members = sorted(f"{tag.id}:{tag.name}" for tag in tags)
    return hashlib.sha256("\n".join(members).encode()).hexdigest()


def get_tag_duplicate_groups(
    *, session: Session, owner_id: uuid.UUID
) -> list[list[Tag]]:
    """
    The user's tags that read as the same name, grouped, over the whole
    vocabulary. A group the user dismissed is left out for as long as it is
    exactly the group they dismissed.
    """
    tags = session.exec(select(Tag).where(Tag.owner_id == owner_id)).all()
    by_key: dict[str, list[Tag]] = {}
    for tag in tags:
        by_key.setdefault(_tag_key(tag.name), []).append(tag)
    dismissed = set(
        session.exec(
            select(TagDuplicateDismissal.signature).where(
                TagDuplicateDismissal.owner_id == owner_id
            )
        ).all()
    )
    groups = [
        sorted(group, key=lambda tag: (tag.name.lower(), tag.name))
        for group in by_key.values()
        if len(group) > 1 and _duplicate_signature(group) not in dismissed
    ]
    return sorted(groups, key=lambda group: group[0].name.lower())


def dismiss_tag_duplicates(
    *, session: Session, owner_id: uuid.UUID, tags: Sequence[Tag]
) -> None:
    signature = _duplicate_signature(tags)
    exists = session.exec(
        select(TagDuplicateDismissal).where(
            TagDuplicateDismissal.owner_id == owner_id,
            TagDuplicateDismissal.signature == signature,
        )
    ).first()
    if exists is None:
        session.add(TagDuplicateDismissal(owner_id=owner_id, signature=signature))
        session.commit()


def tag_merge_counts(
    *, session: Session, owner_id: uuid.UUID, source_ids: Sequence[uuid.UUID]
) -> tuple[int, int]:
    """
    How many tasks carry any of `source_ids`, each counted once, as (live,
    archived). Deleted tasks are not counted, as a tag's own count leaves
    them out, though a merge moves them too.
    """
    archived = col(Task.id).in_(archived_task_ids(owner_id))
    carrying = (
        select(TaskTag.task_id)
        .where(col(TaskTag.tag_id).in_(source_ids))
        .distinct()
        .subquery()
    )
    live, archived_count = session.exec(
        select(func.count().filter(~archived), func.count().filter(archived)).where(
            Task.id == carrying.c.task_id,
            not_deleted(Task),
        )
    ).one()
    return live, archived_count


def merge_tags(*, session: Session, target: Tag, sources: Sequence[Tag]) -> None:
    """
    Fold `sources` into `target`: every task carrying a source carries the
    target instead — once, however many of the tags it had — and the sources
    are deleted. Deleted and archived tasks move too, so neither comes back
    later under a name that no longer exists.

    One commit, so a merge either happens whole or not at all
    (FR-01.27).
    """
    source_ids = [source.id for source in sources]
    carrying_target = set(
        session.exec(select(TaskTag.task_id).where(TaskTag.tag_id == target.id)).all()
    )
    links = session.exec(
        select(TaskTag).where(col(TaskTag.tag_id).in_(source_ids))
    ).all()
    for link in links:
        session.delete(link)
        if link.task_id not in carrying_target:
            session.add(TaskTag(task_id=link.task_id, tag_id=target.id))
            carrying_target.add(link.task_id)
    # The links go first: removing a tag takes its links with it in the
    # database, and the unit of work does not know to order them.
    session.flush()
    for source in sources:
        session.delete(source)
    session.commit()


def get_task_tags(
    *, session: Session, task_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """The tag names on each of the given tasks, keyed by task id."""
    if not task_ids:
        return {}

    statement = (
        select(TaskTag.task_id, Tag.name)
        .join(Tag, col(Tag.id) == TaskTag.tag_id)
        .where(col(TaskTag.task_id).in_(task_ids))
    )
    tags: dict[uuid.UUID, list[str]] = {task_id: [] for task_id in task_ids}
    for task_id, name in session.exec(statement).all():
        tags[task_id].append(name)
    return {task_id: sorted(names, key=str.lower) for task_id, names in tags.items()}
