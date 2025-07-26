# views.py
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import Announcement, Society, Member, Invoice, Complaint, BillType
import random
import string
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from io import BytesIO
from datetime import datetime, timedelta, date
from django.db import models
from django.utils import timezone

now = timezone.now()  # This works correctly

def generate_society_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def home(request):
    return render(request, 'society/home.html')

def dashboard(request):
    """Dashboard view that shows appropriate page based on member type"""
    if not request.user.is_authenticated:
        return redirect('login')
        
    try:
        member = Member.objects.get(user=request.user)

        # Define current datetime
        current_datetime = timezone.now()
        current_date = current_datetime.date()

        # Filter out announcements whose due date has passed
        current_date = timezone.now().date()
        announcements = Announcement.objects.filter(
            society=member.society,
        ).filter(
            # Show announcements that either:
            # 1. Have no due date (permanent announcements)
            # 2. Have a due date that hasn't passed yet
            models.Q(due_date__isnull=True) | 
            models.Q(due_date__gte=current_date)
        ).order_by('-created_at')


        # Get active polls
        active_polls = Poll.objects.filter(
            society=member.society,
            is_active=True,
            end_date__gt=current_datetime  # Compare with current_datetime
        ).prefetch_related('options', 'options__votes')

        # Calculate vote percentages for each poll
        for poll in active_polls:
            total_votes = poll.vote_set.count()
            for option in poll.options.all():
                option.vote_percentage = (option.votes.count() / total_votes * 100) if total_votes > 0 else 0
        
        # Get user's voted polls
        voted_polls = Vote.objects.filter(member=member).values_list('poll_id', flat=True)

        # Get announcements due tomorrow
        tomorrow = date.today() + timedelta(days=1)
        upcoming_reminders = Announcement.objects.filter(
            society=member.society,
            due_date=tomorrow
        ).order_by('due_date')

        # Get active bill types for the society
        active_bill_types = BillType.objects.filter(
            society=member.society,
            is_active=True
        ).order_by('bill_number')
        
        context = {
            'society': member.society,
            'member': member,
            'location': f"Building {member.building}-{member.flat_number}, {member.society.name}",
            'announcements': announcements,  # Add this line to include announcements in context
            'active_polls': active_polls,
            'voted_polls': voted_polls,
            'upcoming_reminders': upcoming_reminders,
            'active_bill_types': active_bill_types,  # Add this to context
        }
        
        if member.member_type == 'committee':
            # Get completed polls for committee members
            completed_polls = Poll.objects.filter(
                society=member.society,
                end_date__lte=current_datetime,
            ).prefetch_related('options', 'options__votes').order_by('-end_date')  # Order by most recently ended
            
            # Calculate vote percentages for completed polls
            for poll in completed_polls:
                total_votes = poll.vote_set.count()
                for option in poll.options.all():
                    option.vote_percentage = (option.votes.count() / total_votes * 100) if total_votes > 0 else 0
            
            context['completed_polls'] = completed_polls
            
        return render(request, 
                     'society/home_committee.html' if member.member_type == 'committee' 
                     else 'society/home_residents.html', 
                     context)
        
    except Member.DoesNotExist:
        messages.error(request, 'No membership found.')
        return redirect('login')

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')  # Redirect to dashboard after login
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'society/login.html')

def register_society(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        number_of_members = request.POST.get('number_of_members')
        society_code = generate_society_code()
        
        society = Society.objects.create(
            name=name,
            description=description,
            society_code=society_code,
            number_of_members=number_of_members
        )
        return redirect('signup')
    return render(request, 'society/register_society.html')

def user_logout(request):
    logout(request)
    #messages.success(request, 'Successfully logged out!')
    return redirect('home')

def signup(request):
        #undo here
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        society_code = request.POST.get('society_code')
        member_type = request.POST.get('member_type')
        building = request.POST.get('building')  # New field
        flat_number = request.POST.get('flat_number')  # New field

        if password1 == password2:
            try:
                
                society = Society.objects.get(society_code=society_code)

                # Check if a user with the same building, flat number, and member type already exists
                existing_member = Member.objects.filter(
                    society=society,
                    building=building,
                    flat_number=flat_number,
                    member_type=member_type
                ).exists()

                if existing_member:
                    member_type_display = "Committee Member" if member_type == "committee" else "Regular Member"
                    messages.error(request, f'A {member_type_display} member for Building {building}-{flat_number} already exists.')
                    return redirect('signup')

                user = User.objects.create_user(username=username, password=password1)
                Member.objects.create(
                    user=user,
                    society=society,
                    member_type=member_type,
                    building=building,  # Added this field
                    flat_number=flat_number  # Added this field
                )

                society.number_of_members += 1
                society.save()

                login(request, user)
                return redirect('dashboard')  # Redirect to dashboard after signup
            except Society.DoesNotExist:
                messages.error(request, 'Invalid society code')
            except Exception as e:
                messages.error(request, f'Error creating account: {str(e)}')
        else:
            messages.error(request, 'Passwords do not match')
    
    societies = Society.objects.all()
    return render(request, 'society/signup.html', {'societies': societies})

@login_required
def create_announcement(request):
    try:
        member = Member.objects.get(user=request.user)
        if member.member_type != 'committee':
            messages.error(request, 'Only committee members can create announcements.')
            return redirect('dashboard')
            
        if request.method == 'POST':
            title = request.POST.get('title')
            content = request.POST.get('content')
            due_date = request.POST.get('due_date')
            
            if title and content:
                Announcement.objects.create(
                    society=member.society,
                    title=title,
                    content=content,
                    created_by=member,
                    due_date=due_date if due_date else None
                )
                messages.success(request, 'Announcement created successfully!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Both title and content are required.')
                
        return render(request, 'society/announcement_committee.html', {
            'member': member,
            'society': member.society
        })
    except Member.DoesNotExist:
        messages.error(request, 'No membership found.')
        return redirect('login')
    
from django.utils import timezone
from .models import Poll, PollOption, Vote
from django.db.models import Count

@login_required
def generate_poll(request):
    try:
        member = Member.objects.get(user=request.user)
        if member.member_type != 'committee':
            messages.error(request, 'Only committee members can create polls.')
            return redirect('dashboard')
            
        if request.method == 'POST':
            question = request.POST.get('question')
            end_date = request.POST.get('end_date')
            
            if question and end_date:
                # Create poll
                poll = Poll.objects.create(
                    society=member.society,
                    question=question,
                    created_by=member,
                    end_date=end_date
                )
                
                # Create options
                for i in range(1, 5):
                    option_text = request.POST.get(f'option{i}')
                    if option_text:
                        PollOption.objects.create(
                            poll=poll,
                            option_text=option_text
                        )
                
                messages.success(request, 'Poll created successfully!')
                return redirect('dashboard')
            else:
                messages.error(request, 'All fields are required.')
                
        return render(request, 'society/generate_poll.html', {
            'member': member,
            'society': member.society,
            'location': f"Building {member.building}-{member.flat_number}, {member.society.name}"
        })
    except Member.DoesNotExist:
        messages.error(request, 'No membership found.')
        return redirect('login')

@login_required
def vote_poll(request, poll_id):
    if request.method == 'POST':
        try:
            poll = Poll.objects.get(id=poll_id)
            member = Member.objects.get(user=request.user)
            option_id = request.POST.get('option')
            
            if not poll.is_active or poll.end_date < timezone.now():
                messages.error(request, 'This poll has ended.')
                return redirect('dashboard')
            
            # Check if user already voted
            if Vote.objects.filter(poll=poll, member=member).exists():
                messages.error(request, 'You have already voted in this poll.')
                return redirect('dashboard')
            
            option = PollOption.objects.get(id=option_id, poll=poll)
            Vote.objects.create(poll=poll, option=option, member=member)
            messages.success(request, 'Vote recorded successfully!')
            
        except (Poll.DoesNotExist, PollOption.DoesNotExist):
            messages.error(request, 'Invalid poll or option.')
            
    return redirect('dashboard')

@login_required
def generate_invoice_pdf(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Check if the invoice belongs to the logged-in user
        if invoice.member.user != request.user:
            messages.error(request, 'Unauthorized access to invoice.')
            return redirect('dashboard')
        
        # Create a file-like buffer to receive PDF data
        buffer = BytesIO()
        
        # Create the PDF object using the buffer as its "file"
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Draw things on the PDF
        # Header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, 750, invoice.member.society.name)
        
        p.setFont("Helvetica", 12)
        p.drawString(50, 730, f"Invoice #{invoice.invoice_number}")
        p.drawString(50, 710, f"Date: {invoice.issue_date.strftime('%B %d, %Y')}")
        
        # Member Details
        p.drawString(50, 670, "Bill To:")
        p.drawString(50, 650, f"{invoice.member.user.get_full_name() or invoice.member.user.username}")
        p.drawString(50, 630, f"Building {invoice.member.building} - Flat {invoice.member.flat_number}")
        
        # Invoice Details
        data = [
            ["Description", "Amount"],
            [invoice.description, f"₹{invoice.amount}"],
            ["", ""],
            ["Total", f"₹{invoice.amount}"]
        ]
        
        table = Table(data, colWidths=[300, 100])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        table.wrapOn(p, 400, 400)
        table.drawOn(p, 50, 550)
        
        # Payment Details
        p.drawString(50, 450, "Payment Details:")
        p.drawString(50, 430, f"Due Date: {invoice.due_date.strftime('%B %d, %Y')}")
        p.drawString(50, 410, f"Status: {invoice.status.upper()}")
        
        # Footer
        p.setFont("Helvetica", 8)
        p.drawString(50, 50, "This is a computer-generated invoice and doesn't require a signature.")
        
        # Close the PDF object cleanly
        p.showPage()
        p.save()
        
        # Get the value of the BytesIO buffer and write it to the response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        
        return response
        
    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found.')
        return redirect('dashboard')

@login_required
def billing_payment(request):
    try:
        member = Member.objects.get(user=request.user)
        invoices = Invoice.objects.filter(member=member).order_by('-created_at')
        
        context = {
            'member': member,
            'invoices': invoices,
            'location': f"Building {member.building}-{member.flat_number}, {member.society.name}"
        }
        
        return render(request, 'society/billing_payment.html', context)
    except Member.DoesNotExist:
        messages.error(request, 'No membership found.')
        return redirect('login')
    
#undo here for complaints
@login_required
def submit_complaint(request):
    try:
        member = Member.objects.get(user=request.user)
        
        if request.method == 'POST':
            title = request.POST.get('title')
            description = request.POST.get('description')
            
            if title and description:
                Complaint.objects.create(
                    title=title,
                    description=description,
                    created_by=member,
                    society=member.society
                )
                messages.success(request, 'Complaint submitted successfully!')
                return redirect('view_complaints')
            else:
                messages.error(request, 'Both title and description are required.')
                
        return render(request, 'society/submit_complaint.html', {
            'member': member,
            'society': member.society,
            'location': f"Building {member.building}-{member.flat_number}, {member.society.name}"
        })
    except Member.DoesNotExist:
        messages.error(request, 'No membership found.')
        return redirect('login')

@login_required
def view_complaints(request):
    try:
        member = Member.objects.get(user=request.user)
        
        # Committee members can see all complaints for their society
        if member.member_type == 'committee':
            complaints = Complaint.objects.filter(society=member.society)
        else:
            # Regular members can only see their own complaints
            complaints = Complaint.objects.filter(created_by=member)
            
        return render(request, 'society/view_complaints.html', {
            'complaints': complaints,
            'member': member,
            'society': member.society,
            'location': f"Building {member.building}-{member.flat_number}, {member.society.name}"
        })
    except Member.DoesNotExist:
        messages.error(request, 'No membership found.')
        return redirect('login')

@login_required
def update_complaint_status(request, complaint_id):
    if request.method == 'POST':
        try:
            member = Member.objects.get(user=request.user)
            if member.member_type != 'committee':
                messages.error(request, 'Only committee members can update complaint status.')
                return redirect('view_complaints')
                
            complaint = Complaint.objects.get(id=complaint_id, society=member.society)
            new_status = request.POST.get('status')
            committee_notes = request.POST.get('committee_notes')
            
            complaint.status = new_status
            complaint.committee_notes = committee_notes
            if new_status == 'resolved':
                complaint.resolved_at = timezone.now()
            complaint.save()
            
            messages.success(request, 'Complaint status updated successfully!')
        except Complaint.DoesNotExist:
            messages.error(request, 'Complaint not found.')
        except Member.DoesNotExist:
            messages.error(request, 'No membership found.')
            
    return redirect('view_complaints')

#undo here for reminders

@login_required
def add_bill_type(request):
    if request.method == 'POST':
        try:
            member = Member.objects.get(user=request.user)
            if member.member_type != 'committee':
                messages.error(request, 'Only committee members can add bill types.')
                return redirect('dashboard')
                
            bill_number = request.POST.get('bill_number')
            description = request.POST.get('description')
            qr_code = request.FILES.get('qr_code')  # Add this line
            due_date_str = request.POST.get('due_date')

            # Parse the datetime string correctly
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    messages.error(request, 'Invalid date format. Please try again.')
                    return redirect('dashboard')
            else:
                due_date = None
            
            BillType.objects.create(
                society=member.society,
                bill_number=bill_number,
                description=description,
                created_by=member,
                qr_code=qr_code,  # Add this line
                due_date=due_date if due_date else None
            )
            
            #messages.success(request, 'Bill type added successfully!')
            
        except Member.DoesNotExist:
            messages.error(request, 'No membership found.')
            
    return redirect('dashboard')

@login_required
def toggle_bill_status(request, bill_id):
    if request.method == 'POST':
        try:
            member = Member.objects.get(user=request.user)
            if member.member_type != 'committee':
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'})
                
            bill_type = BillType.objects.get(id=bill_id, society=member.society)
            bill_type.is_active = not bill_type.is_active
            bill_type.save()
            
            return JsonResponse({'status': 'success'})
            
        except (Member.DoesNotExist, BillType.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Not found'})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def delete_bill_type(request, bill_id):
    if request.method == 'POST':
        try:
            member = Member.objects.get(user=request.user)
            if member.member_type != 'committee':
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'})
                
            bill_type = BillType.objects.get(id=bill_id, society=member.society)
            bill_type.delete()
            
            return JsonResponse({'status': 'success'})
            
        except (Member.DoesNotExist, BillType.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'Not found'})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def view_bill_qr(request, bill_id):
    try:
        member = Member.objects.get(user=request.user)
        bill = BillType.objects.get(id=bill_id, society=member.society)
        return render(request, 'society/view_bill_qr.html', {
            'bill': bill,
            'member': member,
            'location': f"Building {member.building}-{member.flat_number}, {member.society.name}"
        })
    except (Member.DoesNotExist, BillType.DoesNotExist):
        messages.error(request, 'Bill not found.')
        return redirect('dashboard')