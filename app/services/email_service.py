import os
import smtplib
from email.message import EmailMessage
from html import escape


class EmailService:
    def _get_smtp_settings(self) -> dict[str, str | int]:
        smtp_host = (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip()
        smtp_port = int((os.getenv("SMTP_PORT") or "587").strip())
        smtp_username = (os.getenv("SMTP_USERNAME") or "").strip()
        smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
        smtp_from = (os.getenv("SMTP_FROM_EMAIL") or smtp_username).strip()

        if not smtp_username or not smtp_password or not smtp_from:
            raise RuntimeError("Missing SMTP configuration for email service.")

        return {
            "host": smtp_host,
            "port": smtp_port,
            "username": smtp_username,
            "password": smtp_password,
            "from_email": smtp_from,
        }

    def _build_base_email_html(
        self,
        title: str,
        greeting_name: str,
        body_content: str,
        notification_type: str = "Account Security",
        otp_box: str = "",
        footer_note: str = ""
    ) -> str:
        safe_name = escape(greeting_name) if greeting_name else ""
        greeting = f"Namaste {safe_name}," if safe_name else "Namaste,"

        otp_html = ""
        if otp_box:
            otp_html = f"""
                    <!-- OTP BOX SECTION -->
                    <tr>
                        <td class="otp-sec" style="padding: 0 40px 30px 40px;">
                            <div class="otp-box" style="background-color: #2563eb; background-image: linear-gradient(90deg, #1d4ed8 0%, #2563eb 50%, #38bdf8 100%); border-radius: 16px; padding: 32px 20px; text-align: center; box-shadow: 0 12px 24px rgba(37, 99, 235, 0.25);">
                                <p style="margin: 0 0 10px 0; font-size: 12px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: #e0f2fe;">
                                    Your One-Time Code
                                </p>
                                <div class="otp-number" style="margin: 0; font-size: 40px; line-height: 1; letter-spacing: 0.3em; font-weight: 800; color: #ffffff; text-indent: 0.3em;">
                                    {otp_box}
                                </div>
                            </div>
                        </td>
                    </tr>
            """

        footer_html = ""
        if footer_note:
            footer_html = f"""
                                        <p class="body-text" style="margin: 0 0 10px 0; font-size: 13px; line-height: 1.6; color: #64748b; font-weight: 600;">
                                            {footer_note}
                                        </p>
            """

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; line-height: 100%; outline: none; text-decoration: none; }}
        
        @media only screen and (max-width: 600px) {{
            .wrapper-padding {{ padding: 24px 12px !important; }}
            .main-card {{ border-radius: 20px !important; }}
            .header-sec {{ padding: 32px 24px 20px 24px !important; }}
            .content-sec {{ padding: 0 24px 10px 24px !important; }}
            .otp-sec {{ padding: 0 24px 30px 24px !important; }}
            .footer-sec {{ padding: 0 24px 32px 24px !important; }}
            .title-text {{ font-size: 24px !important; line-height: 1.2 !important; margin-bottom: 8px !important; }}
            .body-text {{ font-size: 14px !important; line-height: 1.6 !important; }}
            .otp-box {{ padding: 24px 16px !important; border-radius: 14px !important; }}
            .otp-number {{ font-size: 32px !important; letter-spacing: 0.2em !important; text-indent: 0.2em !important; }}
            .header-table {{ width: 100% !important; }}
            .mobile-badge-wrap {{ display: block !important; padding-left: 0 !important; margin-top: 14px !important; }}
        }}
    </style>
</head>
<body style="margin:0; padding:0; background-color:#ffffff; font-family:'Plus Jakarta Sans', Arial, Helvetica, sans-serif; color:#0f172a; -webkit-font-smoothing: antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#ffffff;">
        <tr>
            <td align="center" class="wrapper-padding" style="padding: 40px 16px;">
                <!--[if mso | IE]>
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="520" align="center"><tr><td>
                <![endif]-->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" class="main-card" style="max-width:520px; width:100%; background-color:#f6f8fc; border:1px solid #cbd5e1; border-radius:24px; overflow:hidden; box-shadow:0 24px 60px rgba(15, 23, 42, 0.08);">
                    <tr>
                        <td class="header-sec" style="padding: 40px 40px 20px 40px;">
                            <table role="presentation" cellspacing="0" cellpadding="0" class="header-table">
                                <tr>
                                    <td valign="middle">
                                        <img src="https://wohlhpljogdykiiipwjk.supabase.co/storage/v1/object/public/careersathi/career_counselor.png" alt="Career Sathi" style="height: 46px; width: auto; max-width: 200px; display: block; border-radius: 8px; box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);">
                                    </td>
                                    <td valign="middle" class="mobile-badge-wrap" style="padding-left: 18px;">
                                        <span style="display:inline-block; font-size:11px; font-weight:700; letter-spacing:0.16em; text-transform:uppercase; color:#0b3f9b; padding:6px 14px; border-radius:999px; border:1px solid rgba(59, 130, 246, 0.3); background-color:rgba(59, 130, 246, 0.14);">
                                            {notification_type}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td class="content-sec" style="padding: 0 40px 10px 40px;">
                            <h1 class="title-text" style="margin: 0 0 14px 0; font-size: 28px; line-height: 1.1; font-weight: 800; letter-spacing: -0.02em; color: #0f172a;">
                                {title}
                            </h1>
                            <p class="body-text" style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #475569; font-weight: 500;">
                                {greeting}
                            </p>
                            <p class="body-text" style="margin: 0 0 24px 0; font-size: 15px; line-height: 1.6; color: #475569;">
                                {body_content}
                            </p>
                        </td>
                    </tr>
                    {otp_html}
                    <tr>
                        <td class="footer-sec" style="padding: 0 40px 40px 40px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-top: 1px solid #cbd5e1; margin-top: 10px; padding-top: 24px;">
                                <tr>
                                    <td>
                                        {footer_html}
                                        <p class="body-text" style="margin: 0 0 24px 0; font-size: 13px; line-height: 1.6; color: #64748b;">
                                            This is an automated message from Career Sathi. Please do not reply to this email.
                                        </p>
                                        <p style="margin: 0; font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #94a3b8; text-align: center;">
                                            CAREER SATHI AI
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
                <!--[if mso | IE]>
                </td></tr></table>
                <![endif]-->
            </td>
        </tr>
    </table>
</body>
</html>
"""

    def _send_email(self, email: str, subject: str, html_content: str, text_content: str):
        smtp_settings = self._get_smtp_settings()

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp_settings["from_email"]
        message["To"] = email
        message.set_content(text_content)
        message.add_alternative(html_content, subtype="html")

        try:
            with smtplib.SMTP(smtp_settings["host"], int(smtp_settings["port"])) as smtp:
                smtp.starttls()
                smtp.login(smtp_settings["username"], smtp_settings["password"])
                smtp.send_message(message)
        except Exception as e:
            print(f"Failed to send email to {email}: {e}")
            raise e

    def send_otp_email(self, email: str, otp_code: str):
        safe_email = escape(email)
        safe_otp = escape(otp_code)
        body_content = f"We received a request to reset the password for your account associated with <strong style=\"color: #0f172a;\">{safe_email}</strong>. Please use the verification code below to securely change your password."
        footer_note = "<span style=\"color: #b91c1c;\">Note:</span> This code expires in 10 minutes and can only be used once."
        
        html_content = self._build_base_email_html(
            title="Password Reset",
            greeting_name="",
            body_content=body_content,
            notification_type="Account Security",
            otp_box=safe_otp,
            footer_note=footer_note
        )
        
        text_content = f"Your Career Sathi password reset OTP is {otp_code}. It expires in 10 minutes."
        
        self._send_email(email, "Your Career Sathi password reset OTP", html_content, text_content)

    def send_welcome_email(self, email: str, full_name: str):
        body_content = "Welcome to <strong style=\"color: #0f172a;\">Career Sathi</strong>! We're thrilled to have you onboard. Career Sathi will help you navigate your educational and professional future seamlessly. Start by completing your profile and exploring personalized career roadmaps."
        
        html_content = self._build_base_email_html(
            title="Welcome to Career Sathi",
            greeting_name=full_name,
            body_content=body_content,
            notification_type="Welcome",
            footer_note="If you didn't create this account, please ignore this email."
        )
        
        text_content = f"Welcome to Career Sathi, {full_name}! We're thrilled to have you onboard."
        
        self._send_email(email, "Welcome to Career Sathi!", html_content, text_content)

    def send_report_ready_email(self, email: str, full_name: str):
        body_content = "Great news! Your personalized <strong style=\"color: #0f172a;\">Career Prediction Report</strong> has been successfully generated based on your profile and inputs. You can now log into your Career Sathi dashboard to view your new career matches, read the analysis, and explore the interactive roadmap."
        
        html_content = self._build_base_email_html(
            title="Your Career Report is Ready",
            greeting_name=full_name,
            body_content=body_content,
            notification_type="Career Insights",
            footer_note="You can view and export your report from your dashboard at any time."
        )
        
        text_content = f"Great news, {full_name}! Your personalized Career Pattern Report is ready on your dashboard."
        
        self._send_email(email, "Your Career Report is Ready!", html_content, text_content)

    def send_password_reset_success_email(self, email: str):
        body_content = f"The password for your account associated with <strong style=\"color: #0f172a;\">{escape(email)}</strong> has been successfully changed.<br><br>If you made this change, you don't need to do anything else."
        
        html_content = self._build_base_email_html(
            title="Password Changed",
            greeting_name="",
            body_content=body_content,
            notification_type="Account Security",
            footer_note="<span style=\"color: #b91c1c;\">If you did not make this change, please contact support immediately.</span>"
        )
        
        text_content = "Your password has been successfully changed. If you did not make this change, please contact support immediately."
        
        self._send_email(email, "Your Career Sathi Password was Changed", html_content, text_content)

email_service = EmailService()
