class HashAlgorithm:
    name: str

class SHA256(HashAlgorithm):
    digest_size: int

__all__ = ["HashAlgorithm", "SHA256"]
