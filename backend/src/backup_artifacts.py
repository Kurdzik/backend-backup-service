import base64
import gzip
import json
import os
import shutil
from hashlib import sha256

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENCRYPTED_MAGIC = b"BBSENC1\n"


def compress_file(path: str) -> str:
    compressed_path = f"{path}.gz"
    with open(path, "rb") as source, gzip.open(compressed_path, "wb") as target:
        shutil.copyfileobj(source, target)
    return compressed_path


def decompress_file(path: str) -> str:
    decompressed_path = path.removesuffix(".gz") if path.endswith(".gz") else f"{path}.decompressed"
    with gzip.open(path, "rb") as source, open(decompressed_path, "wb") as target:
        shutil.copyfileobj(source, target)
    return decompressed_path


def is_encrypted_file(path: str) -> bool:
    try:
        with open(path, "rb") as file:
            return file.read(len(ENCRYPTED_MAGIC)) == ENCRYPTED_MAGIC
    except FileNotFoundError:
        return False


def is_gzip_file(path: str) -> bool:
    try:
        with open(path, "rb") as file:
            return file.read(2) == b"\x1f\x8b"
    except FileNotFoundError:
        return False


def public_key_fingerprint(public_key_pem: str) -> str:
    return sha256(public_key_pem.strip().encode("utf-8")).hexdigest()


def encrypt_file(path: str, public_key_pem: str) -> str:
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    file_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)

    with open(path, "rb") as source:
        plaintext = source.read()

    ciphertext = AESGCM(file_key).encrypt(nonce, plaintext, None)
    encrypted_file_key = public_key.encrypt(
        file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    header = {
        "encrypted_key": base64.b64encode(encrypted_file_key).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "key_fingerprint": public_key_fingerprint(public_key_pem),
        "original_name": os.path.basename(path),
    }

    encrypted_path = f"{path}.enc"
    with open(encrypted_path, "wb") as target:
        target.write(ENCRYPTED_MAGIC)
        target.write(json.dumps(header).encode("utf-8"))
        target.write(b"\n")
        target.write(ciphertext)

    return encrypted_path


def decrypt_file(path: str, private_key_pem: str) -> str:
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )

    with open(path, "rb") as source:
        magic = source.readline()
        if magic != ENCRYPTED_MAGIC:
            raise ValueError("Backup is not encrypted")
        header = json.loads(source.readline().decode("utf-8"))
        ciphertext = source.read()

    encrypted_file_key = base64.b64decode(header["encrypted_key"])
    nonce = base64.b64decode(header["nonce"])
    file_key = private_key.decrypt(
        encrypted_file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    plaintext = AESGCM(file_key).decrypt(nonce, ciphertext, None)
    if path.endswith(".enc"):
        decrypted_path = path.removesuffix(".enc")
    else:
        original_name = header.get("original_name", "decrypted")
        decrypted_path = f"{path}.{original_name}"

    with open(decrypted_path, "wb") as target:
        target.write(plaintext)

    return decrypted_path
