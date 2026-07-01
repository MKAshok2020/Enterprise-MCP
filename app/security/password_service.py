"""Password hashing and verification."""

import bcrypt


class PasswordService:
    """Secure password service backed by bcrypt."""

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password."""
        password_bytes = password.encode("utf-8")
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a hash."""
        password_bytes = password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)

