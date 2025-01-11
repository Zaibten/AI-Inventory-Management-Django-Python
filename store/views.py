"""
Module: store.views

Contains Django views for managing items, profiles,
and deliveries in the store application.

Classes handle product listing, creation, updating,
deletion, and delivery management.
The module integrates with Django's authentication
and querying functionalities.
"""

# Standard library imports
import operator
from functools import reduce
from statistics import LinearRegression
from turtle import pd

# Django core imports
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum

# Authentication and permissions
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Class-based views
from django.views.generic import (
    DetailView, CreateView, UpdateView, DeleteView, ListView
)
from django.views.generic.edit import FormMixin

# Third-party packages
from django_tables2 import SingleTableView
import django_tables2 as tables
from django_tables2.export.views import ExportMixin

# Local app imports
from accounts.models import Customer, Profile, Vendor
from bills.views import send_email_alert
from transactions.models import Sale, SaleDetail
from .models import Category, Item, Delivery
from .forms import ItemForm, CategoryForm, DeliveryForm
from .tables import ItemTable

# For SMTP Mail Server for Notify users
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Item


@login_required
def dashboard(request):
    send_email_alert()
    print("Running low-quantity check on startup...")
    notify_low_quantity_items()
    profiles = Profile.objects.all()
    Category.objects.annotate(nitem=Count("item"))
    items = Item.objects.all()
    total_items = (
        Item.objects.all()
        .aggregate(Sum("quantity"))
        .get("quantity__sum", 0.00)
    )
    items_count = items.count()
    profiles_count = profiles.count()

    # Prepare data for charts
    category_counts = Category.objects.annotate(
        item_count=Count("item")
    ).values("name", "item_count")
    categories = [cat["name"] for cat in category_counts]
    category_counts = [cat["item_count"] for cat in category_counts]

    sale_dates = (
        Sale.objects.values("date_added__date")
        .annotate(total_sales=Sum("grand_total"))
        .order_by("date_added__date")
    )
    sale_dates_labels = [
        date["date_added__date"].strftime("%Y-%m-%d") for date in sale_dates
    ]
    sale_dates_values = [float(date["total_sales"]) for date in sale_dates]
    low_stock_threshold = 20  # threshold for low stock
    low_stock_items = Item.objects.filter(quantity__lte=low_stock_threshold)
    low_stock_items_names = [item.name for item in low_stock_items]
    low_stock_items_counts = [item.quantity for item in low_stock_items]
    duplicate_items = (
        Item.objects.values('name')
        .annotate(name_count=Count('name'))
        .filter(name_count__gt=1)
    )
    duplicate_products = Item.objects.filter(
        name__in=[item['name'] for item in duplicate_items]
    ).order_by('price')
    first_duplicate_products = []
    seen_names = set()
    for product in duplicate_products:
        if product.name not in seen_names:
            first_duplicate_products.append(product)
            seen_names.add(product.name)

    pending_delivery_count = Delivery.objects.filter(is_delivered=False).count()
    items_not_sold = Item.objects.exclude(
        id__in=SaleDetail.objects.values('item').distinct()
    )
    items_in_sales = Item.objects.filter(
        id__in=SaleDetail.objects.values('item').distinct()
    )
    customer_loyalty_data = {
        'labels': [f'{customer.first_name} {customer.last_name}' for customer in Customer.objects.all()],
        'data': [customer.loyalty_points for customer in Customer.objects.all()],
        'title': 'Customer Loyalty Points Distribution',
        'subtitle': 'Loyalty points per customer'
    }
    category_data = Category.objects.annotate(
        total_price=Sum("item__price"),
        total_quantity=Sum("item__quantity")
    ).values("name", "total_price", "total_quantity")
    categories_names = [data["name"] for data in category_data]
    total_prices = [data["total_price"] for data in category_data]
    total_quantities = [data["total_quantity"] for data in category_data]
    category_data = Category.objects.annotate(
        total_price=Sum("item__price"),
        total_quantity=Sum("item__quantity")
    ).values("name", "total_price", "total_quantity")
    categories_names = [data["name"] for data in category_data]
    total_prices = [data["total_price"] for data in category_data]
    total_quantities = [data["total_quantity"] for data in category_data]
    tips = []
    tips_labels = []
    tips_importance = []
    if low_stock_items_names:
        tips.append(f"Tip: Consider restocking items such as {', '.join(low_stock_items_names)} to avoid stockouts.")
        tips_labels.append("Restock items")
        tips_importance.append(90)
    slow_selling_items = Item.objects.exclude(
        id__in=SaleDetail.objects.values('item').distinct()
    )
    if slow_selling_items:
        tips.append(f"Tip: Consider offering discounts on slow-moving products like {', '.join([item.name for item in slow_selling_items])} to boost sales.")
        tips_labels.append("Discount slow movers")
        tips_importance.append(75)
    high_loyalty_customers = Customer.objects.filter(loyalty_points__gt=100)
    if high_loyalty_customers:
        tips.append(f"Tip: Offer exclusive deals to loyal customers with over 100 loyalty points.")
        tips_labels.append("Loyalty points")
        tips_importance.append(85)

    sales_growth = sale_dates_values[-1] - sale_dates_values[0] if sale_dates_values else 0
    if sales_growth > 1000:
        tips.append(f"Tip: Sales have grown by {sales_growth} this month. Consider scaling up inventory.")
        tips_labels.append("Sales Growth")
        tips_importance.append(95)

    if total_items < 500:
        tips.append("Tip: Consider diversifying your product range to offer more variety.")
        tips_labels.append("Product Balance")
        tips_importance.append(80)
    if sale_dates_values and max(sale_dates_values) > 5000:
        tips.append(f"Tip: High sales demand detected. Restock popular items immediately to meet demand.")
        tips_labels.append("Restock Demand")
        tips_importance.append(90)
    tips.append("Tip: Launch loyalty programs to incentivize repeat purchases.")
    tips_labels.append("Launch Loyalty Program")
    tips_importance.append(80)
    tips.append("Tip: Monitor supplier performance to ensure timely deliveries and quality products.")
    tips_labels.append("Supplier Performance")
    tips_importance.append(85)
    tips.append("Tip: Evaluate marketing campaigns to focus on the most successful strategies.")
    tips_labels.append("Marketing Strategies")
    tips_importance.append(75)
    tips.append("Tip: Train staff regularly to enhance customer service and operational efficiency.")
    tips_labels.append("Staff Training")
    tips_importance.append(80)
    tips.append("Tip: Invest in technology upgrades to streamline inventory and sales tracking.")
    tips_labels.append("Technology Upgrade")
    tips_importance.append(90)
    tips.append("Tip: Conduct customer surveys to gather insights on preferences and satisfaction.")
    tips_labels.append("Customer Insights")
    tips_importance.append(70)
    tips.append("Tip: Implement eco-friendly practices to attract environmentally conscious customers.")
    tips_labels.append("Eco-Friendly Practices")
    tips_importance.append(75)
    tips.append("Tip: Keep a close eye on competitors to adapt pricing and offerings as needed.")
    tips_labels.append("Competitive Analysis")
    tips_importance.append(85)
    if sale_dates_labels and 'December' in sale_dates_labels[-1]:
        tips.append("Tip: Optimize inventory ahead of the holiday season to meet increased demand.")
        tips_labels.append("Seasonal Inventory")
        tips_importance.append(85)

    tips.append("Tip: Improve product descriptions and images to enhance customer experience and boost conversion rates.")
    tips_labels.append("Improve Descriptions")
    tips_importance.append(75)
    tips_labels = [
        "Monitor stock", 
        "Discount items", 
        "Loyalty points", 
        "Analyze patterns", 
        "Balance sales", 
        "Optimize storage", 
        "Audit inventory", 
        "Fast updates", 
        "Track turnover", 
        "Order accuracy",
        "Restock demand", 
        "Launch promotions", 
        "Seasonal inventory",
        "Improve descriptions"
    ]
    tips_importance = [80, 70, 90, 80, 100, 70, 90, 60, 80, 90, 90, 75, 85, 80, 70]
    tips_labels = [
        "Monitor stock", 
        "Discount items", 
        "Loyalty points", 
        "Analyze patterns", 
        "Balance sales", 
        "Optimize storage", 
        "Audit inventory", 
        "Fast updates", 
        "Track turnover", 
        "Order accuracy"
    ]
    tips_importance = [80, 70, 90, 80, 100, 70, 90, 60, 80, 90]
    sales_trend_data = (
        SaleDetail.objects.filter(item__in=items_in_sales)
        .values("item__name", "sale__date_added__date")
        .annotate(total_quantity=Sum("quantity"))
        .order_by("sale__date_added__date")
    )
    sales_trend_labels = [
        entry["sale__date_added__date"].strftime("%Y-%m-%d") for entry in sales_trend_data
    ]
    sales_trend_values = [entry["total_quantity"] for entry in sales_trend_data]
    context = {
        "items": items,
        "profiles": profiles,
        "profiles_count": profiles_count,
        "items_count": items_count,
        "total_items": total_items,
        "vendors": Vendor.objects.all(),
        "delivery": Delivery.objects.all(),
        "pending_delivery_count": pending_delivery_count,
        "sales": Sale.objects.all(),
        "customer_loyalty_data": customer_loyalty_data,
        "categories": categories,
        "category_counts": category_counts,
        "sale_dates_labels": sale_dates_labels,
        "sale_dates_values": sale_dates_values,
        "low_stock_items_names": low_stock_items_names,
        "low_stock_items_counts": low_stock_items_counts,
        "duplicate_products": first_duplicate_products,  # Add filtered duplicates to context
        "items_not_sold": items_not_sold,  # Add less sold items to the context
        "categories_names": categories_names,
        "total_prices": total_prices,
        "total_quantities": total_quantities,
        "tips": tips,  # Add tips to context
        "tips_labels": tips_labels,
        "tips_importance": tips_importance,
        "items_in_sales": items_in_sales,
        "sales_trend_labels":sales_trend_labels,
        "sales_trend_values": sales_trend_values,
        "tips_importance": tips_importance,
    }
    return render(request, "store/dashboard.html", context)

class ProductListView(LoginRequiredMixin, ExportMixin, tables.SingleTableView):
    """
    View class to display a list of products.

    Attributes:
    - model: The model associated with the view.
    - table_class: The table class used for rendering.
    - template_name: The HTML template used for rendering the view.
    - context_object_name: The variable name for the context object.
    - paginate_by: Number of items per page for pagination.
    """

    model = Item
    table_class = ItemTable
    template_name = "store/productslist.html"
    context_object_name = "items"
    paginate_by = 10
    SingleTableView.table_pagination = False


class ItemSearchListView(ProductListView):
    """
    View class to search and display a filtered list of items.

    Attributes:
    - paginate_by: Number of items per page for pagination.
    """

    paginate_by = 10

    def get_queryset(self):
        result = super(ItemSearchListView, self).get_queryset()

        query = self.request.GET.get("q")
        if query:
            query_list = query.split()
            result = result.filter(
                reduce(
                    operator.and_, (Q(name__icontains=q) for q in query_list)
                )
            )
        return result


class ProductDetailView(LoginRequiredMixin, FormMixin, DetailView):
    """
    View class to display detailed information about a product.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    """

    model = Item
    template_name = "store/productdetail.html"

    def get_success_url(self):
        return reverse("product-detail", kwargs={"slug": self.object.slug})


class ProductCreateView(LoginRequiredMixin, CreateView):
    """
    View class to create a new product.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    - form_class: The form class used for data input.
    - success_url: The URL to redirect to upon successful form submission.
    """

    model = Item
    template_name = "store/productcreate.html"
    form_class = ItemForm
    success_url = "/products"

    def test_func(self):
        # item = Item.objects.get(id=pk)
        if self.request.POST.get("quantity") < 1:
            return False
        else:
            return True


class ProductUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    View class to update product information.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    - fields: The fields to be updated.
    - success_url: The URL to redirect to upon successful form submission.
    """

    model = Item
    template_name = "store/productupdate.html"
    form_class = ItemForm
    success_url = "/products"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        else:
            return False


class ProductDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View class to delete a product.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    - success_url: The URL to redirect to upon successful deletion.
    """

    model = Item
    template_name = "store/productdelete.html"
    success_url = "/products"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        else:
            return False


class DeliveryListView(
    LoginRequiredMixin, ExportMixin, tables.SingleTableView
):
    """
    View class to display a list of deliveries.

    Attributes:
    - model: The model associated with the view.
    - pagination: Number of items per page for pagination.
    - template_name: The HTML template used for rendering the view.
    - context_object_name: The variable name for the context object.
    """

    model = Delivery
    pagination = 10
    template_name = "store/deliveries.html"
    context_object_name = "deliveries"


class DeliverySearchListView(DeliveryListView):
    """
    View class to search and display a filtered list of deliveries.

    Attributes:
    - paginate_by: Number of items per page for pagination.
    """

    paginate_by = 10

    def get_queryset(self):
        result = super(DeliverySearchListView, self).get_queryset()

        query = self.request.GET.get("q")
        if query:
            query_list = query.split()
            result = result.filter(
                reduce(
                    operator.
                    and_, (Q(customer_name__icontains=q) for q in query_list)
                )
            )
        return result


class DeliveryDetailView(LoginRequiredMixin, DetailView):
    """
    View class to display detailed information about a delivery.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    """

    model = Delivery
    template_name = "store/deliverydetail.html"


class DeliveryCreateView(LoginRequiredMixin, CreateView):
    """
    View class to create a new delivery.

    Attributes:
    - model: The model associated with the view.
    - fields: The fields to be included in the form.
    - template_name: The HTML template used for rendering the view.
    - success_url: The URL to redirect to upon successful form submission.
    """

    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryUpdateView(LoginRequiredMixin, UpdateView):
    """
    View class to update delivery information.

    Attributes:
    - model: The model associated with the view.
    - fields: The fields to be updated.
    - template_name: The HTML template used for rendering the view.
    - success_url: The URL to redirect to upon successful form submission.
    """

    model = Delivery
    form_class = DeliveryForm
    template_name = "store/delivery_form.html"
    success_url = "/deliveries"


class DeliveryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View class to delete a delivery.

    Attributes:
    - model: The model associated with the view.
    - template_name: The HTML template used for rendering the view.
    - success_url: The URL to redirect to upon successful deletion.
    """

    model = Delivery
    template_name = "store/productdelete.html"
    success_url = "/deliveries"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        else:
            return False


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'store/category_list.html'
    context_object_name = 'categories'
    paginate_by = 10
    login_url = 'login'


class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = Category
    template_name = 'store/category_detail.html'
    context_object_name = 'category'
    login_url = 'login'


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    template_name = 'store/category_form.html'
    form_class = CategoryForm
    login_url = 'login'

    def get_success_url(self):
        return reverse_lazy('category-detail', kwargs={'pk': self.object.pk})


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    template_name = 'store/category_form.html'
    form_class = CategoryForm
    login_url = 'login'

    def get_success_url(self):
        return reverse_lazy('category-detail', kwargs={'pk': self.object.pk})


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'store/category_confirm_delete.html'
    context_object_name = 'category'
    success_url = reverse_lazy('category-list')
    login_url = 'login'


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

# Store the last email timestamp in memory
LAST_EMAIL_TIMESTAMP = None

def notify_low_quantity_items():
    """
    Notify about items with low quantity (less than 15).
    Sends email only if the last email was sent more than 60 minutes ago.
    """
    global LAST_EMAIL_TIMESTAMP  # Use global to access and update the timestamp

    current_time = time.time()
    if LAST_EMAIL_TIMESTAMP:
        if current_time - LAST_EMAIL_TIMESTAMP < 3600:  # 60 minutes
            print("Email was sent less than an hour ago. Skipping notification.")
            return

    low_quantity_items = Item.objects.filter(quantity__lt=15)
    if not low_quantity_items.exists():
        print("No items with low quantity found.")
        return

    # Email configuration
    sender_email = "muzamilkhanofficial786@gmail.com"
    sender_password = "iaqu xvna tpix ugkt"
    #recipient_email = "rimshayounus3@gmail.com"
    recipient_email = "muzamilkhanofficials@gmail.com"
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    subject = "🔔 Low Stock Alert | AutoInven"
    email_body = """
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 10px; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
            <div style="text-align: center; padding-bottom: 20px;">
                <img src="cid:logo" alt="AutoInven Logo" style="max-width: 110px; height: 110px; border-radius: 50%;" />
                <h2 style="color: #333;">AutoInven - Inventory Management</h2>
                <p style="color: #555;">🚨 Attention! The following items need restocking:</p>
            </div>
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding: 10px; background: #f1f1f1; border: 1px solid #ddd;">Product Name</th>
                        <th style="text-align: left; padding: 10px; background: #f1f1f1; border: 1px solid #ddd;">Category</th>
                        <th style="text-align: left; padding: 10px; background: #f1f1f1; border: 1px solid #ddd;">Quantity</th>
                        <th style="text-align: left; padding: 10px; background: #f1f1f1; border: 1px solid #ddd;">Vendor</th>
                    </tr>
                </thead>
                <tbody>
    """

    for item in low_quantity_items:
        vendor_name = item.vendor.name if item.vendor else "N/A"
        email_body += f"""
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;">{item.name}</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{item.category.name}</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{item.quantity}</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{vendor_name}</td>
        </tr>
        """

    email_body += """
                </tbody>
            </table>
            <p style="color: #333; text-align: center; margin-top: 20px;">
                🛒 Please consider placing a new order for the above items to ensure smooth operations.
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

            # Attach logo as inline image
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


# Automatically run notify_low_quantity_items() on startup
@receiver(post_migrate)
def check_low_quantity(sender, **kwargs):
    """
    Signal to automatically check for low-quantity items after migrations.
    """
    print("Running low-quantity check...")
    notify_low_quantity_items()

@csrf_exempt
@require_POST
@login_required
def get_items_ajax_view(request):
    if is_ajax(request):
        try:
            term = request.POST.get("term", "")
            data = []

            items = Item.objects.filter(name__icontains=term)
            for item in items[:10]:
                data.append(item.to_json())

            return JsonResponse(data, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Not an AJAX request'}, status=400)
