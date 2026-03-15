import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { messagesApi } from "../api/endpoints";
import { EmptyState, PageHeader, Panel, StatusBadge } from "../components/ui";
import {
  type ChatKeyBundle,
  bootstrapChatKeys,
  decryptDirectMessage,
  encryptDirectMessage,
  restoreChatPrivateKey,
  unlockChatPrivateKey
} from "../lib/chatCrypto";
import { formatDateTime } from "../lib/format";
import { useAuthStore } from "../store/auth";

function contactLabel(contact: any) {
  return contact.name || contact.email;
}

function contactInitials(contact: any) {
  const source = (contact.name || contact.email || "PCM").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

function messageTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(date);
}

function hasKeyBundle(bundle?: ChatKeyBundle | null) {
  return Boolean(bundle?.public_key && bundle?.private_key_encrypted && bundle?.key_salt && bundle?.key_iv);
}

export default function MessagesPage() {
  const client = useQueryClient();
  const { user } = useAuthStore();
  const roles = user?.roles || [];
  const canView = roles.some((role) => ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin", "general_user"].includes(role));
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [contactSearch, setContactSearch] = useState("");
  const [composer, setComposer] = useState("");
  const [unlockPassword, setUnlockPassword] = useState("");
  const [unlockError, setUnlockError] = useState("");
  const [actionError, setActionError] = useState("");
  const [privateKey, setPrivateKey] = useState<CryptoKey | null>(null);
  const [decryptedMessages, setDecryptedMessages] = useState<Record<number, string>>({});
  const requestedThreadId = (() => {
    const rawValue = searchParams.get("thread");
    if (!rawValue) return null;
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) ? parsed : null;
  })();

  const keyBundleQuery = useQuery({
    queryKey: ["chat-key-bundle"],
    queryFn: messagesApi.getKeyBundle,
    enabled: canView
  });
  const contactsQuery = useQuery({
    queryKey: ["message-contacts"],
    queryFn: messagesApi.contacts,
    enabled: canView,
    refetchInterval: 60_000
  });
  const conversationsQuery = useQuery({
    queryKey: ["message-conversations"],
    queryFn: messagesApi.conversations,
    enabled: canView,
    refetchInterval: 5_000
  });
  const messagesQuery = useQuery({
    queryKey: ["message-thread", selectedThreadId],
    queryFn: () => messagesApi.listMessages(selectedThreadId as number),
    enabled: canView && Boolean(selectedThreadId),
    refetchInterval: 5_000
  });

  useEffect(() => {
    let active = true;

    async function restoreKey() {
      if (!keyBundleQuery.data) {
        if (active) setPrivateKey(null);
        return;
      }

      try {
        const restored = await restoreChatPrivateKey(keyBundleQuery.data);
        if (active) {
          setPrivateKey(restored);
        }
      } catch {
        if (active) {
          setPrivateKey(null);
        }
      }
    }

    void restoreKey();
    return () => {
      active = false;
    };
  }, [
    keyBundleQuery.data?.public_key,
    keyBundleQuery.data?.private_key_encrypted,
    keyBundleQuery.data?.key_salt,
    keyBundleQuery.data?.key_iv
  ]);

  function selectConversation(threadId: number) {
    setSelectedThreadId(threadId);
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("thread", String(threadId));
    setSearchParams(nextSearchParams, { replace: true });
  }

  useEffect(() => {
    if (!conversationsQuery.data?.length) return;

    if (requestedThreadId) {
      const requestedExists = conversationsQuery.data.some((conversation: any) => conversation.id === requestedThreadId);
      if (requestedExists) {
        if (selectedThreadId !== requestedThreadId) {
          setSelectedThreadId(requestedThreadId);
        }
        return;
      }
    }

    if (!selectedThreadId) {
      selectConversation(conversationsQuery.data[0].id);
    }
  }, [conversationsQuery.data, requestedThreadId, searchParams, selectedThreadId, setSearchParams]);

  useEffect(() => {
    let active = true;

    async function decryptMessages() {
      if (!messagesQuery.data || !privateKey || !user?.id) {
        if (active) setDecryptedMessages({});
        return;
      }

      const entries = await Promise.all(
        messagesQuery.data.map(async (message: any) => {
          try {
            return [message.id, await decryptDirectMessage(message, privateKey, user.id)] as const;
          } catch {
            return [message.id, "Unable to decrypt this message on this device."] as const;
          }
        })
      );

      if (active) {
        setDecryptedMessages(Object.fromEntries(entries));
      }
    }

    void decryptMessages();
    return () => {
      active = false;
    };
  }, [messagesQuery.data, privateKey, user?.id]);

  useEffect(() => {
    if (!selectedThreadId || !messagesQuery.data || !user?.id) return;
    const hasUnread = messagesQuery.data.some((message: any) => message.sender_user_id !== user.id && !message.read_at);
    if (!hasUnread) return;

    void messagesApi.markRead(selectedThreadId).then(async () => {
      await client.invalidateQueries({ queryKey: ["message-conversations"] });
      await client.invalidateQueries({ queryKey: ["message-thread", selectedThreadId] });
    }).catch(() => undefined);
  }, [client, messagesQuery.data, selectedThreadId, user?.id]);

  const normalizedSearch = contactSearch.trim().toLowerCase();
  const filteredConversations = useMemo(() => {
    const source = conversationsQuery.data || [];
    if (!normalizedSearch) return source;

    return source.filter((conversation: any) => {
      const primaryContact = conversation.participants?.[0];
      return [
        primaryContact?.name,
        primaryContact?.email,
        primaryContact?.university_name,
        conversation.last_message_preview
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedSearch));
    });
  }, [conversationsQuery.data, normalizedSearch]);

  const searchResults = useMemo(() => {
    if (!normalizedSearch) return [];

    const matchedConversationUserIds = new Set(
      filteredConversations.flatMap((conversation: any) => (conversation.participants || []).map((participant: any) => participant.id))
    );

    return (contactsQuery.data || [])
      .filter((contact: any) =>
        [contact.name, contact.email, contact.university_name]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalizedSearch))
      )
      .filter((contact: any) => !matchedConversationUserIds.has(contact.id))
      .slice(0, 8);
  }, [contactsQuery.data, filteredConversations, normalizedSearch]);

  const selectedConversation = useMemo(
    () => (conversationsQuery.data || []).find((conversation: any) => conversation.id === selectedThreadId) || null,
    [conversationsQuery.data, selectedThreadId]
  );

  const secureChatReady = Boolean(privateKey && keyBundleQuery.data?.public_key);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  async function unlockSecureChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUnlockError("");
    setActionError("");

    if (!unlockPassword.trim()) {
      setUnlockError("Enter your account password to unlock secure chat.");
      return;
    }

    try {
      let nextPrivateKey: CryptoKey | null = null;
      if (hasKeyBundle(keyBundleQuery.data)) {
        nextPrivateKey = await unlockChatPrivateKey(keyBundleQuery.data, unlockPassword);
      } else {
        const bundle = await bootstrapChatKeys(unlockPassword, messagesApi.getKeyBundle, messagesApi.setKeyBundle);
        await client.invalidateQueries({ queryKey: ["chat-key-bundle"] });
        nextPrivateKey = await restoreChatPrivateKey(bundle);
      }

      setPrivateKey(nextPrivateKey);
      setUnlockPassword("");
    } catch {
      setUnlockError("Unable to unlock secure chat with that password.");
    }
  }

  async function openConversation(contact: any) {
    setActionError("");
    if (!contact.chat_public_key) {
      setActionError(`${contactLabel(contact)} has not activated secure chat yet.`);
      return;
    }

    try {
      const conversation = await messagesApi.startDirectConversation({ recipient_user_id: contact.id });
      await client.invalidateQueries({ queryKey: ["message-conversations"] });
      selectConversation(conversation.id);
      setContactSearch("");
    } catch (error: any) {
      setActionError(error?.response?.data?.detail || "Unable to open the conversation.");
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!secureChatReady || !selectedThreadId || !selectedConversation || !user?.id || !keyBundleQuery.data?.public_key) return;

    const trimmedBody = composer.trim();
    if (!trimmedBody) return;

    const recipients = [
      { id: user.id, publicKey: keyBundleQuery.data.public_key },
      ...(selectedConversation.participants || [])
        .filter((participant: any) => participant.chat_public_key)
        .map((participant: any) => ({ id: participant.id, publicKey: participant.chat_public_key as string }))
    ];

    try {
      const encryptedPayload = await encryptDirectMessage(trimmedBody, recipients);
      await messagesApi.sendMessage(selectedThreadId, encryptedPayload);
      setComposer("");
      await client.invalidateQueries({ queryKey: ["message-thread", selectedThreadId] });
      await client.invalidateQueries({ queryKey: ["message-conversations"] });
    } catch (error: any) {
      setActionError(error?.response?.data?.detail || "Unable to send the encrypted message.");
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Network communication"
        title="Messages"
        description="Direct messages are end-to-end encrypted between participants, with a Messenger-style workspace for cross-campus collaboration."
      />

      <div className="messages-shell">
        <Panel className="messages-sidebar">
          <div className="messages-sidebar-content">
            <div>
              <p className="eyebrow">Private chat</p>
              <h3 className="text-xl font-semibold text-slate-950">Recent chats</h3>
            </div>

            <label className="field-shell">
              <span className="field-label">Search for a person</span>
              <input
                className="field-input"
                value={contactSearch}
                onChange={(event) => setContactSearch(event.target.value)}
                placeholder="Search by name, email, or university"
              />
            </label>

            <div className="messages-section messages-section-fill">
              <div className="messages-section-head">
                <span>Recent chats</span>
                <StatusBadge label={`${filteredConversations.length} threads`} tone="neutral" />
              </div>
              <div className="messages-list">
                {filteredConversations.length === 0 && searchResults.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    {normalizedSearch ? "No people or conversations match that search." : "No conversations yet."}
                  </p>
                ) : (
                  <>
                    {filteredConversations.map((conversation: any) => {
                      const primaryContact = conversation.participants?.[0];
                      return (
                        <button
                          key={conversation.id}
                          type="button"
                          className={["conversation-card", selectedThreadId === conversation.id ? "conversation-card-active" : ""].join(" ").trim()}
                          onClick={() => selectConversation(conversation.id)}
                        >
                          <div className="conversation-avatar">{contactInitials(primaryContact || { name: "PCM" })}</div>
                          <div className="min-w-0 flex-1 text-left">
                            <div className="flex items-center justify-between gap-3">
                              <p className="truncate text-sm font-semibold text-slate-900">{contactLabel(primaryContact || { email: "Conversation" })}</p>
                              {conversation.unread_count ? <span className="conversation-unread">{conversation.unread_count}</span> : null}
                            </div>
                            <p className="truncate text-xs text-slate-500">{primaryContact?.university_name || "PCM network"}</p>
                            <p className="mt-1 truncate text-sm text-slate-500">{conversation.last_message_preview || "Start an encrypted conversation"}</p>
                          </div>
                        </button>
                      );
                    })}

                    {searchResults.length > 0 ? (
                      <>
                        <p className="messages-list-label">People</p>
                        {searchResults.map((contact: any) => (
                          <button
                            key={contact.id}
                            type="button"
                            className="contact-card"
                            onClick={() => void openConversation(contact)}
                          >
                            <div className="conversation-avatar">{contactInitials(contact)}</div>
                            <div className="min-w-0 flex-1 text-left">
                              <div className="flex items-center justify-between gap-2">
                                <p className="truncate text-sm font-semibold text-slate-900">{contactLabel(contact)}</p>
                                <StatusBadge label={contact.chat_public_key ? "Ready" : "Pending"} tone={contact.chat_public_key ? "success" : "warning"} />
                              </div>
                              <p className="truncate text-xs text-slate-500">{contact.university_name || contact.email}</p>
                            </div>
                          </button>
                        ))}
                      </>
                    ) : null}
                  </>
                )}
              </div>
            </div>
          </div>
        </Panel>

        <Panel className="messages-panel">
          {!secureChatReady ? (
            <div className="messages-lock-state">
              <div className="space-y-3">
                <p className="eyebrow">Encrypted access</p>
                <h3 className="text-2xl font-semibold text-slate-950">
                  {hasKeyBundle(keyBundleQuery.data) ? "Unlock secure chat on this device" : "Activate secure chat"}
                </h3>
                <p className="max-w-xl text-sm leading-7 text-slate-600">
                  {hasKeyBundle(keyBundleQuery.data)
                    ? "Use your account password to decrypt your message key and read private conversations on this browser."
                    : "Your first secure-chat login will generate a public and private key pair in the browser, then store only the encrypted private key on the server."}
                </p>
              </div>

              <form className="grid max-w-md gap-4" onSubmit={unlockSecureChat}>
                <label className="field-shell">
                  <span className="field-label">Account password</span>
                  <input
                    className="field-input"
                    type="password"
                    value={unlockPassword}
                    onChange={(event) => setUnlockPassword(event.target.value)}
                    placeholder="Enter password to unlock"
                  />
                </label>
                {unlockError ? <p className="rounded-[14px] bg-rose-50 px-4 py-3 text-sm text-rose-700">{unlockError}</p> : null}
                <button className="primary-button justify-center" type="submit">
                  {hasKeyBundle(keyBundleQuery.data) ? "Unlock messages" : "Activate secure chat"}
                </button>
              </form>
            </div>
          ) : selectedConversation ? (
            <>
              <div className="messages-header">
                <div className="flex items-center gap-3">
                  <div className="conversation-avatar conversation-avatar-lg">
                    {contactInitials(selectedConversation.participants?.[0] || { name: "PCM" })}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-950">
                      {contactLabel(selectedConversation.participants?.[0] || { email: "Conversation" })}
                    </h3>
                    <p className="text-xs text-slate-500">{selectedConversation.participants?.[0]?.university_name || "PCM network"}</p>
                  </div>
                </div>
                <div className="messages-header-badge">
                  <StatusBadge label="End-to-end encrypted" tone="success" />
                </div>
              </div>

              <div className="messages-thread">
                {(messagesQuery.data || []).length === 0 ? (
                  <EmptyState
                    title="No messages yet"
                    description="Start the conversation. The first message will be encrypted in the browser before it is sent."
                  />
                ) : (
                  (messagesQuery.data || []).map((message: any) => {
                    const isOwn = message.sender_user_id === user?.id;
                    return (
                      <div key={message.id} className={["message-row", isOwn ? "message-row-own" : ""].join(" ").trim()}>
                        <div className={["message-bubble", isOwn ? "message-bubble-own" : "message-bubble-peer"].join(" ").trim()}>
                          <p className="text-sm leading-7">{decryptedMessages[message.id] || "Decrypting..."}</p>
                          <div className="message-meta">
                            <span>{isOwn ? "You" : message.sender_name || "PCM member"}</span>
                            <span>{messageTime(message.created_at)}</span>
                            {isOwn && message.read_at ? <span>Read</span> : null}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <form className="messages-composer" onSubmit={sendMessage}>
                <div className="field-shell flex-1">
                  <span className="field-label">Message</span>
                  <textarea
                    className="field-input min-h-[76px]"
                    value={composer}
                    onChange={(event) => setComposer(event.target.value)}
                    placeholder="Write an encrypted message..."
                  />
                </div>
                <button className="primary-button justify-center" type="submit">
                  Send securely
                </button>
              </form>
            </>
          ) : (
            <div className="messages-empty">
              <EmptyState
                title="No recent conversation selected"
                description="Choose a recent encrypted conversation from the sidebar to read and reply."
              />
            </div>
          )}

          {actionError ? <p className="rounded-[14px] bg-rose-50 px-4 py-3 text-sm text-rose-700">{actionError}</p> : null}
          {selectedConversation?.last_message_at ? (
            <p className="text-xs text-slate-500">Latest activity: {formatDateTime(selectedConversation.last_message_at)}</p>
          ) : null}
        </Panel>
      </div>
    </div>
  );
}
