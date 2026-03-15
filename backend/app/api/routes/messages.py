from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import ChatMessage, ChatParticipant, ChatThread, User
from ...schemas import (
    ChatContactRead,
    ChatConversationCreate,
    ChatConversationRead,
    ChatKeyBundleRead,
    ChatKeyBundleUpdate,
    ChatMessageCreate,
    ChatMessageRead,
)
from ...services.rbac import get_user_roles
from ..deps import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


def _serialize_contact(db: Session, user: User) -> ChatContactRead:
    return ChatContactRead(
        id=user.id,
        email=user.email,
        name=user.name,
        university_id=user.university_id or (user.member.university_id if user.member else None),
        university_name=(
            user.university.name
            if user.university
            else (user.member.university.name if user.member and user.member.university else None)
        ),
        member_id=str(user.member.id) if user.member else None,
        member_number=user.member.member_id if user.member else None,
        roles=get_user_roles(db, user),
        chat_public_key=user.chat_public_key,
    )


def _ensure_participant(db: Session, thread_id: int, user_id: int) -> ChatThread:
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not any(participant.user_id == user_id for participant in thread.participants):
        raise HTTPException(status_code=403, detail="You are not a participant in this conversation")
    return thread


def _serialize_conversation(db: Session, thread: ChatThread, current_user_id: int) -> ChatConversationRead:
    other_participants = [
        _serialize_contact(db, participant.user)
        for participant in sorted(thread.participants, key=lambda item: item.user.name or item.user.email)
        if participant.user_id != current_user_id and participant.user
    ]
    last_message = max(thread.messages, key=lambda item: item.created_at, default=None)
    unread_count = len(
        [message for message in thread.messages if message.sender_user_id != current_user_id and message.read_at is None]
    )
    return ChatConversationRead(
        id=thread.id,
        participants=other_participants,
        last_message_preview=(
            "Encrypted message"
            if last_message and last_message.ciphertext
            else (last_message.body[:120] if last_message and last_message.body else None)
        ),
        last_message_at=last_message.created_at if last_message else thread.updated_at,
        unread_count=unread_count,
    )


def _serialize_message(message: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=message.id,
        thread_id=message.thread_id,
        sender_user_id=message.sender_user_id,
        sender_name=message.sender.name if message.sender else None,
        sender_university_name=message.sender.university.name if message.sender and message.sender.university else None,
        body=message.body,
        ciphertext=message.ciphertext,
        iv=message.iv,
        algorithm=message.algorithm,
        key_envelopes=message.key_envelopes or {},
        is_encrypted=bool(message.ciphertext),
        created_at=message.created_at,
        read_at=message.read_at,
    )


def _find_direct_thread(db: Session, user_a_id: int, user_b_id: int) -> ChatThread | None:
    candidate_threads = (
        db.query(ChatThread)
        .join(ChatParticipant)
        .filter(ChatParticipant.user_id.in_([user_a_id, user_b_id]))
        .distinct()
        .all()
    )
    for thread in candidate_threads:
        participant_ids = {participant.user_id for participant in thread.participants}
        if participant_ids == {user_a_id, user_b_id} and len(participant_ids) == 2:
            return thread
    return None


@router.get("/contacts", response_model=list[ChatContactRead])
def list_contacts(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    contacts = (
        db.query(User)
        .filter(User.is_active.is_(True), User.id != user.id)
        .order_by(User.name.asc(), User.email.asc())
        .all()
    )
    return [_serialize_contact(db, item) for item in contacts]


@router.get("/e2ee-key-bundle", response_model=ChatKeyBundleRead)
def get_key_bundle(user=Depends(get_current_user)):
    return ChatKeyBundleRead(
        public_key=user.chat_public_key,
        private_key_encrypted=user.chat_private_key_encrypted,
        key_salt=user.chat_key_salt,
        key_iv=user.chat_key_iv,
        key_algorithm=user.chat_key_algorithm,
    )


@router.put("/e2ee-key-bundle", response_model=ChatKeyBundleRead)
def upsert_key_bundle(
    payload: ChatKeyBundleUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user.chat_public_key = payload.public_key
    user.chat_private_key_encrypted = payload.private_key_encrypted
    user.chat_key_salt = payload.key_salt
    user.chat_key_iv = payload.key_iv
    user.chat_key_algorithm = payload.key_algorithm
    db.commit()
    db.refresh(user)
    return ChatKeyBundleRead(
        public_key=user.chat_public_key,
        private_key_encrypted=user.chat_private_key_encrypted,
        key_salt=user.chat_key_salt,
        key_iv=user.chat_key_iv,
        key_algorithm=user.chat_key_algorithm,
    )


@router.get("/conversations", response_model=list[ChatConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    threads = (
        db.query(ChatThread)
        .join(ChatParticipant)
        .filter(ChatParticipant.user_id == user.id)
        .order_by(ChatThread.updated_at.desc(), ChatThread.id.desc())
        .all()
    )
    return [_serialize_conversation(db, thread, user.id) for thread in threads]


@router.post("/conversations/direct", response_model=ChatConversationRead)
def start_direct_conversation(
    payload: ChatConversationCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if payload.recipient_user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot start a conversation with yourself")

    recipient = db.query(User).filter(User.id == payload.recipient_user_id, User.is_active.is_(True)).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if not user.chat_public_key:
        raise HTTPException(status_code=400, detail="Activate secure chat before starting a conversation")
    if not recipient.chat_public_key:
        raise HTTPException(status_code=400, detail="Recipient has not activated secure chat yet")

    thread = _find_direct_thread(db, user.id, recipient.id)
    if not thread:
        thread = ChatThread()
        db.add(thread)
        db.flush()
        db.add(ChatParticipant(thread_id=thread.id, user_id=user.id))
        db.add(ChatParticipant(thread_id=thread.id, user_id=recipient.id))
        db.commit()
        db.refresh(thread)

    return _serialize_conversation(db, thread, user.id)


@router.get("/conversations/{thread_id}", response_model=list[ChatMessageRead])
def list_messages(
    thread_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    thread = _ensure_participant(db, thread_id, user.id)
    messages = sorted(thread.messages, key=lambda item: item.created_at)
    return [_serialize_message(message) for message in messages]


@router.post("/conversations/{thread_id}/messages", response_model=ChatMessageRead)
def send_message(
    thread_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    thread = _ensure_participant(db, thread_id, user.id)
    body = (payload.body or "").strip()
    has_encrypted_payload = bool(payload.ciphertext and payload.iv and payload.key_envelopes)
    if not has_encrypted_payload and not body:
        raise HTTPException(status_code=400, detail="Message payload is required")

    participant_ids = {str(participant.user_id) for participant in thread.participants}
    if has_encrypted_payload and not participant_ids.issubset(set(payload.key_envelopes.keys())):
        raise HTTPException(status_code=400, detail="Missing encrypted key envelope for one or more participants")

    thread.updated_at = datetime.utcnow()
    message = ChatMessage(
        thread_id=thread.id,
        sender_user_id=user.id,
        body=body or None,
        ciphertext=payload.ciphertext,
        iv=payload.iv,
        algorithm=payload.algorithm or "AES-GCM",
        key_envelopes=payload.key_envelopes or None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return _serialize_message(message)


@router.post("/conversations/{thread_id}/read")
def mark_messages_read(
    thread_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    thread = _ensure_participant(db, thread_id, user.id)
    updated = 0
    for message in thread.messages:
        if message.sender_user_id != user.id and message.read_at is None:
            message.read_at = datetime.utcnow()
            updated += 1
    db.commit()
    return {"updated": updated}
