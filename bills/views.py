# Django core imports
from django.urls import reverse

# Class-based views
from django.views.generic import (
    CreateView,
    UpdateView,
    DeleteView
)

# Authentication and permissions
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Third-party packages
from django_tables2 import SingleTableView
from django_tables2.export.views import ExportMixin

# Local app imports
from .models import Bill
from .tables import BillTable
from accounts.models import Profile


# SMTP Email Service
import time
import smtplib
from django.http import HttpResponse
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.mail import send_mail
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from .models import Bill
import time

# Store the last email timestamp in memory
LAST_EMAIL_TIMESTAMP = None


class BillListView(LoginRequiredMixin, ExportMixin, SingleTableView):
    """View for listing bills."""
    model = Bill
    table_class = BillTable
    template_name = 'bills/bill_list.html'
    context_object_name = 'bills'
    paginate_by = 10
    SingleTableView.table_pagination = False

    def get_context_data(self, **kwargs):
        # Call the base method to get the context data
        context = super().get_context_data(**kwargs)

        # Send email alert when this view is accessed
        send_email_alert()

        # Add any additional context here if needed
        return context


class BillCreateView(LoginRequiredMixin, CreateView):
    """View for creating a new bill."""
    model = Bill
    template_name = 'bills/billcreate.html'
    fields = [
        'institution_name',
        'phone_number',
        'email',
        'address',
        'description',
        'payment_details',
        'amount',
        'status'
    ]

    def get_success_url(self):
        """Redirect to the list of bills after a successful update."""
        return reverse('bill_list')


class BillUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating an existing bill."""
    model = Bill
    template_name = 'bills/billupdate.html'
    fields = [
        'institution_name',
        'phone_number',
        'email',
        'address',
        'description',
        'payment_details',
        'amount',
        'status'
    ]

    def test_func(self):
        """Check if the user has the required permissions."""
        return self.request.user.profile in Profile.objects.all()

    def get_success_url(self):
        """Redirect to the list of bills after a successful update."""
        return reverse('bill_list')


class BillDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting a bill."""
    model = Bill
    template_name = 'bills/billdelete.html'

    def test_func(self):
        """Check if the user is a superuser."""
        return self.request.user.is_superuser

    def get_success_url(self):
        """Redirect to the list of bills after successful deletion."""
        return reverse('bill_list')


def send_email_alert():
    global LAST_EMAIL_TIMESTAMP  # Use global to access and update the timestamp

    current_time = time.time()
    
    # If email was sent less than 60 minutes ago, skip sending email
    if LAST_EMAIL_TIMESTAMP and current_time - LAST_EMAIL_TIMESTAMP < 3600:
        print("Email was sent less than 60 minutes ago. Skipping notification.")
        return

    # Find pending bills
    pending_bills = Bill.objects.filter(status=False)

    if not pending_bills.exists():
        print("No pending bills found.")
        return

    # Email configuration
    sender_email = "muzamilkhanofficial786@gmail.com"
    sender_password = "iaqu xvna tpix ugkt"
    recipient_email = "muzamilkhanofficials@gmail.com"
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    subject = "💡 Pending Bills Alert"
    email_body = """
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 10px; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
                <div style="text-align: center; padding-bottom: 20px;">
                    <img src="cid:logo" alt="AutoInven Logo" style="max-width: 110px; height: 110px; border-radius: 50%;" />
                    <h2 style="color: #333;">AutoInven - Pending Bill Alert</h2>
                    <p style="color: #555;">🚨 The following bills are pending payment:</p>
                </div>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <thead>
                        <tr>
                            <th style="text-align: left; padding: 10px; background: #f1f1f1; border: 1px solid #ddd;">Institution Name</th>
                            <th style="text-align: left; padding: 10px; background: #f1f1f1; border: 1px solid #ddd;">Description</th>
                            <th style="text-align: left; padding: 10px; background: #f1f1f1; border: 1px solid #ddd;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
        """
    for bill in pending_bills:
        email_body += f"""
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;">{bill.institution_name}</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{bill.description}</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{bill.amount}</td>
        </tr>
        """

    email_body += """
                </tbody>
            </table>
            <p style="color: #333; text-align: center; margin-top: 20px;">
                🛒 Please process the payments for the above bills.
            </p>
            <footer style="text-align: center; margin-top: 30px; color: #777; font-size: 12px;">
                <p>© 2025 AutoInven - All rights reserved.</p>
            </footer>
        </div>
    </body>
    </html>
    """

    try:
        # Create SMTP connection
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)

            # Create email message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject

            # Attach the HTML email body
            msg.attach(MIMEText(email_body, 'html'))

            # Attach logo as inline image (if needed)
            logo_path = r"E:\Inventory Management System FYP\Web Application\Inventory Management System Python Django\static\images\logo\logo.png"
            with open(logo_path, "rb") as logo:
                mime_logo = MIMEImage(logo.read())
                mime_logo.add_header('Content-ID', '<logo>')
                msg.attach(mime_logo)

            # Send the email
            server.sendmail(sender_email, recipient_email, msg.as_string())
            print("Email sent successfully.")

            # Update the in-memory timestamp
            LAST_EMAIL_TIMESTAMP = current_time

    except smtplib.SMTPException as e:
        print(f"Error sending email: {e}")

# Receiver function to handle post_migrate signal
@receiver(post_migrate)
def bill_pending_alert_on_migrate(sender, **kwargs):
    """
    Sends an alert email about pending bills after migrations are completed.
    """
    send_email_alert()