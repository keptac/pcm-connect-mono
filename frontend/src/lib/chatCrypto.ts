const encoder = new TextEncoder();
const decoder = new TextDecoder();

const RSA_KEYGEN_ALGORITHM: RsaHashedKeyGenParams = {
  name: "RSA-OAEP",
  modulusLength: 2048,
  publicExponent: new Uint8Array([1, 0, 1]),
  hash: "SHA-256"
};

const RSA_IMPORT_ALGORITHM: RsaHashedImportParams = {
  name: "RSA-OAEP",
  hash: "SHA-256"
};

const WRAP_KEY_STORAGE = "pcm_chat_wrap_key";
const PBKDF2_ITERATIONS = 250_000;

export type ChatKeyBundle = {
  public_key?: string | null;
  private_key_encrypted?: string | null;
  key_salt?: string | null;
  key_iv?: string | null;
  key_algorithm?: string | null;
};

export type EncryptableParticipant = {
  id: number;
  publicKey: string;
};

export type EncryptedMessagePayload = {
  body?: string | null;
  ciphertext?: string | null;
  iv?: string | null;
  algorithm?: string | null;
  key_envelopes?: Record<string, string>;
};

function bytesToBase64(bytes: Uint8Array) {
  let binary = "";
  bytes.forEach((value) => {
    binary += String.fromCharCode(value);
  });
  return btoa(binary);
}

function base64ToBytes(value: string) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function randomBase64(size: number) {
  return bytesToBase64(crypto.getRandomValues(new Uint8Array(size)));
}

function hasPersistedBundle(bundle: ChatKeyBundle | null | undefined): bundle is Required<ChatKeyBundle> {
  return Boolean(
    bundle?.public_key &&
    bundle?.private_key_encrypted &&
    bundle?.key_salt &&
    bundle?.key_iv
  );
}

async function deriveWrappingKey(password: string, saltBase64: string) {
  const baseKey = await crypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: base64ToBytes(saltBase64),
      iterations: PBKDF2_ITERATIONS,
      hash: "SHA-256"
    },
    baseKey,
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt", "decrypt"]
  );
}

async function decryptPrivateKeyBytes(bundle: Required<ChatKeyBundle>, wrappingKey: CryptoKey) {
  return crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64ToBytes(bundle.key_iv) },
    wrappingKey,
    base64ToBytes(bundle.private_key_encrypted)
  );
}

async function importPublicKey(value: string) {
  return crypto.subtle.importKey("spki", base64ToBytes(value), RSA_IMPORT_ALGORITHM, false, ["encrypt"]);
}

async function decryptPrivateKey(bundle: Required<ChatKeyBundle>, wrappingKey: CryptoKey) {
  const privateKeyBytes = await decryptPrivateKeyBytes(bundle, wrappingKey);
  return crypto.subtle.importKey("pkcs8", privateKeyBytes, RSA_IMPORT_ALGORITHM, false, ["decrypt"]);
}

async function exportSessionWrappingKey(wrappingKey: CryptoKey) {
  const rawKey = await crypto.subtle.exportKey("raw", wrappingKey);
  sessionStorage.setItem(WRAP_KEY_STORAGE, bytesToBase64(new Uint8Array(rawKey)));
}

async function importSessionWrappingKey() {
  const stored = sessionStorage.getItem(WRAP_KEY_STORAGE);
  if (!stored) return null;
  return crypto.subtle.importKey("raw", base64ToBytes(stored), { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

export function clearSessionWrappingKey() {
  sessionStorage.removeItem(WRAP_KEY_STORAGE);
}

export async function bootstrapChatKeys(
  password: string,
  getKeyBundle: () => Promise<ChatKeyBundle>,
  setKeyBundle: (payload: Required<ChatKeyBundle>) => Promise<ChatKeyBundle>
) {
  const existingBundle = await getKeyBundle();
  if (hasPersistedBundle(existingBundle)) {
    const wrappingKey = await deriveWrappingKey(password, existingBundle.key_salt);
    await decryptPrivateKey(existingBundle, wrappingKey);
    await exportSessionWrappingKey(wrappingKey);
    return existingBundle;
  }

  const keyPair = await crypto.subtle.generateKey(RSA_KEYGEN_ALGORITHM, true, ["encrypt", "decrypt"]);
  const publicKey = await crypto.subtle.exportKey("spki", keyPair.publicKey);
  const privateKey = await crypto.subtle.exportKey("pkcs8", keyPair.privateKey);
  const keySalt = randomBase64(16);
  const keyIv = randomBase64(12);
  const wrappingKey = await deriveWrappingKey(password, keySalt);
  const encryptedPrivateKey = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: base64ToBytes(keyIv) },
    wrappingKey,
    privateKey
  );

  const bundle: Required<ChatKeyBundle> = {
    public_key: bytesToBase64(new Uint8Array(publicKey)),
    private_key_encrypted: bytesToBase64(new Uint8Array(encryptedPrivateKey)),
    key_salt: keySalt,
    key_iv: keyIv,
    key_algorithm: "PBKDF2-AES-GCM"
  };

  await setKeyBundle(bundle);
  await exportSessionWrappingKey(wrappingKey);
  return bundle;
}

export async function unlockChatPrivateKey(bundle: ChatKeyBundle, password: string) {
  if (!hasPersistedBundle(bundle)) {
    throw new Error("Secure chat is not set up yet.");
  }
  const wrappingKey = await deriveWrappingKey(password, bundle.key_salt);
  const privateKey = await decryptPrivateKey(bundle, wrappingKey);
  await exportSessionWrappingKey(wrappingKey);
  return privateKey;
}

export async function rotateChatWrappingPassword(
  currentPassword: string,
  nextPassword: string,
  getKeyBundle: () => Promise<ChatKeyBundle>,
  setKeyBundle: (payload: Required<ChatKeyBundle>) => Promise<ChatKeyBundle>
) {
  const existingBundle = await getKeyBundle();
  if (!hasPersistedBundle(existingBundle)) {
    return bootstrapChatKeys(nextPassword, getKeyBundle, setKeyBundle);
  }

  const currentWrappingKey = await deriveWrappingKey(currentPassword, existingBundle.key_salt);
  const privateKeyBytes = await decryptPrivateKeyBytes(existingBundle, currentWrappingKey);
  const nextSalt = randomBase64(16);
  const nextIv = randomBase64(12);
  const nextWrappingKey = await deriveWrappingKey(nextPassword, nextSalt);
  const encryptedPrivateKey = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: base64ToBytes(nextIv) },
    nextWrappingKey,
    privateKeyBytes
  );

  const rotatedBundle: Required<ChatKeyBundle> = {
    public_key: existingBundle.public_key,
    private_key_encrypted: bytesToBase64(new Uint8Array(encryptedPrivateKey)),
    key_salt: nextSalt,
    key_iv: nextIv,
    key_algorithm: existingBundle.key_algorithm || "PBKDF2-AES-GCM"
  };

  await setKeyBundle(rotatedBundle);
  await exportSessionWrappingKey(nextWrappingKey);
  return rotatedBundle;
}

export async function restoreChatPrivateKey(bundle: ChatKeyBundle) {
  if (!hasPersistedBundle(bundle)) {
    return null;
  }
  const wrappingKey = await importSessionWrappingKey();
  if (!wrappingKey) {
    return null;
  }
  return decryptPrivateKey(bundle, wrappingKey);
}

export async function encryptDirectMessage(body: string, participants: EncryptableParticipant[]) {
  const messageKey = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, messageKey, encoder.encode(body));
  const rawMessageKey = await crypto.subtle.exportKey("raw", messageKey);

  const uniqueParticipants = Array.from(
    new Map(participants.filter((participant) => participant.publicKey).map((participant) => [participant.id, participant])).values()
  );

  const keyEnvelopes: Record<string, string> = {};
  for (const participant of uniqueParticipants) {
    const publicKey = await importPublicKey(participant.publicKey);
    const encryptedKey = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, publicKey, rawMessageKey);
    keyEnvelopes[String(participant.id)] = bytesToBase64(new Uint8Array(encryptedKey));
  }

  return {
    ciphertext: bytesToBase64(new Uint8Array(ciphertext)),
    iv: bytesToBase64(iv),
    algorithm: "AES-GCM",
    key_envelopes: keyEnvelopes
  };
}

export async function decryptDirectMessage(
  message: EncryptedMessagePayload,
  privateKey: CryptoKey,
  userId: number
) {
  if (!message.ciphertext || !message.iv) {
    return message.body || "";
  }

  const envelope = message.key_envelopes?.[String(userId)];
  if (!envelope) {
    throw new Error("Missing encrypted key for the current user.");
  }

  const rawMessageKey = await crypto.subtle.decrypt({ name: "RSA-OAEP" }, privateKey, base64ToBytes(envelope));
  const messageKey = await crypto.subtle.importKey("raw", rawMessageKey, { name: "AES-GCM" }, false, ["decrypt"]);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64ToBytes(message.iv) },
    messageKey,
    base64ToBytes(message.ciphertext)
  );
  return decoder.decode(plaintext);
}
