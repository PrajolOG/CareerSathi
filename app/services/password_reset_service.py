import hashlib
import os
import secrets
import smtplib
import threading
import time
from email.message import EmailMessage
from html import escape

from dotenv import load_dotenv
from supabase import create_client
from supabase_auth import AdminUserAttributes

from app.database import url
from app.services.email_service import email_service

load_dotenv()


class PasswordResetService:
    OTP_TTL_SECONDS = 600
    MAX_ATTEMPTS = 5

    def __init__(self):
        self._lock = threading.Lock()
        self._otp_store: dict[str, dict[str, float | int | str]] = {}

    def _normalize_email(self, email: str) -> str:
        return (email or "").strip().lower()

    def _hash_otp(self, otp: str) -> str:
        return hashlib.sha256(otp.encode("utf-8")).hexdigest()

    def _cleanup_expired(self):
        now = time.time()
        expired_emails = [
            email
            for email, data in self._otp_store.items()
            if float(data.get("expires_at", 0)) <= now
        ]
        for email in expired_emails:
            self._otp_store.pop(email, None)

    def _get_admin_client(self):
        service_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not service_key:
            raise RuntimeError("Missing SUPABASE_SERVICE_ROLE_KEY for password reset.")
        return create_client(url, service_key)

    def _find_user_by_email(self, email: str):
        admin_client = self._get_admin_client()
        page = 1

        while True:
            users = admin_client.auth.admin.list_users(page=page, per_page=200)
            if not users:
                return None

            for user in users:
                if self._normalize_email(getattr(user, "email", "")) == email:
                    return user

            if len(users) < 200:
                return None

            page += 1

    def send_reset_otp(self, email: str) -> tuple[bool, str]:
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return False, "Please enter a valid email address."

        try:
            user = self._find_user_by_email(normalized_email)
        except Exception as exc:
            print(f"Password reset setup error: {exc}")
            return False, "Password reset is not configured yet. Please contact support."

        if not user or not getattr(user, "id", None):
            return False, "No account found with that email address."

        otp_code = f"{secrets.randbelow(1_000_000):06d}"

        with self._lock:
            self._cleanup_expired()
            self._otp_store[normalized_email] = {
                "otp_hash": self._hash_otp(otp_code),
                "expires_at": time.time() + self.OTP_TTL_SECONDS,
                "attempts": 0,
                "user_id": str(user.id),
            }

        try:
            email_service.send_otp_email(normalized_email, otp_code)
        except Exception as exc:
            with self._lock:
                self._otp_store.pop(normalized_email, None)
            print(f"Password reset email send failed: {exc}")
            return False, "Could not send OTP email right now. Please try again."

        return True, "We sent a 6-digit OTP to your email."

    def reset_password(self, email: str, otp_code: str, new_password: str) -> tuple[bool, str]:
        normalized_email = self._normalize_email(email)
        clean_otp = (otp_code or "").strip()
        clean_password = (new_password or "").strip()

        if not normalized_email:
            return False, "Missing email address."
        if len(clean_otp) != 6 or not clean_otp.isdigit():
            return False, "Please enter the 6-digit OTP."
        if len(clean_password) < 6:
            return False, "Password must be at least 6 characters long."

        with self._lock:
            self._cleanup_expired()
            otp_record = self._otp_store.get(normalized_email)

            if not otp_record:
                return False, "OTP expired or not requested. Please request a new code."

            if int(otp_record.get("attempts", 0)) >= self.MAX_ATTEMPTS:
                self._otp_store.pop(normalized_email, None)
                return False, "Too many invalid attempts. Please request a new OTP."

            if self._hash_otp(clean_otp) != otp_record.get("otp_hash"):
                otp_record["attempts"] = int(otp_record.get("attempts", 0)) + 1
                return False, "Invalid OTP. Please try again."

            user_id = str(otp_record.get("user_id") or "").strip()

        if not user_id:
            return False, "Reset session is invalid. Please request a new OTP."

        try:
            admin_client = self._get_admin_client()
            admin_client.auth.admin.update_user_by_id(
                user_id,
                AdminUserAttributes(password=clean_password),
            )
        except Exception as exc:
            print(f"Password reset update failed: {exc}")
            return False, "Could not reset the password right now. Please try again."

        with self._lock:
            self._otp_store.pop(normalized_email, None)

        try:
            email_service.send_password_reset_success_email(normalized_email)
        except Exception as exc:
            print(f"Password reset success email failed: {exc}")

        return True, "Password updated successfully. Please log in with your new password."


password_reset_service = PasswordResetService()
