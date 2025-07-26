from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('register-society/', views.register_society, name='register_society'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('create-announcement/', views.create_announcement, name='create_announcement'),
    path('generate-poll/', views.generate_poll, name='generate_poll'),
    path('vote-poll/<int:poll_id>/', views.vote_poll, name='vote_poll'),
    path('generate-invoice-pdf/<int:invoice_id>/', views.generate_invoice_pdf, name='generate_invoice_pdf'),
    path('billing-payment/', views.billing_payment, name='billing_payment'),
    path('submit-complaint/', views.submit_complaint, name='submit_complaint'),
    path('view-complaints/', views.view_complaints, name='view_complaints'),
    path('update-complaint-status/<int:complaint_id>/', views.update_complaint_status, name='update_complaint_status'),
    path('add-bill-type/', views.add_bill_type, name='add_bill_type'),
    path('toggle-bill-status/<int:bill_id>/', views.toggle_bill_status, name='toggle_bill_status'),
    path('delete-bill-type/<int:bill_id>/', views.delete_bill_type, name='delete_bill_type'),
    path('view-bill-qr/<int:bill_id>/', views.view_bill_qr, name='view_bill_qr'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)