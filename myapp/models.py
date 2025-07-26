# models.py
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal

class Society(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    society_code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    number_of_members = models.IntegerField(default=0)  # Add this field

    #undo here
    class Meta:
        verbose_name_plural = "Societies"  # Fixes plural form in admin
        ordering = ['name']  # Orders societies by name

    def __str__(self):
        return self.name

class Member(models.Model):
    MEMBER_TYPES = (
        ('member', 'Regular Member'),
        ('committee', 'Committee Member'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    society = models.ForeignKey(Society, on_delete=models.CASCADE)
    member_type = models.CharField(max_length=10, choices=MEMBER_TYPES)
    building = models.CharField(max_length=50)  # New field
    flat_number = models.CharField(max_length=10)  # New field
    joined_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.member_type == 'committee':
            # Grant admin site access to committee members
            self.user.is_staff = True
            self.user.save()
            
            # Create or get committee group
            committee_group, created = Group.objects.get_or_create(name='Committee Members')
            
            # Add announcement permissions
            content_type = ContentType.objects.get_for_model(Announcement)
            permissions = Permission.objects.filter(content_type=content_type)
            for permission in permissions:
                committee_group.permissions.add(permission)
            
            # Add user to committee group
            self.user.groups.add(committee_group)

    def __str__(self):
        return f"{self.user.username} - {self.society.name}"
    
class Announcement(models.Model):
    society = models.ForeignKey(Society, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Member, on_delete=models.CASCADE)
    due_date = models.DateField(null=True, blank=True)  # New field

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"

    def __str__(self):
        return f"{self.title} - {self.society.name}"
    
class Poll(models.Model):
    society = models.ForeignKey(Society, on_delete=models.CASCADE)
    question = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Member, on_delete=models.CASCADE)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.question

    class Meta:
        ordering = ['-created_at']

class PollOption(models.Model):
    poll = models.ForeignKey(Poll, related_name='options', on_delete=models.CASCADE)
    option_text = models.CharField(max_length=200)
    
    def __str__(self):
        return self.option_text

    def votes_count(self):
        return self.votes.count()

class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    option = models.ForeignKey(PollOption, related_name='votes', on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('poll', 'member')  # Ensures one vote per member per poll

class Invoice(models.Model):
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    )
    
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=20, unique=True)
    issue_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='pending')
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last_invoice = Invoice.objects.order_by('-created_at').first()
            if last_invoice:
                last_number = int(last_invoice.invoice_number[3:])
                self.invoice_number = f'INV{str(last_number + 1).zfill(6)}'
            else:
                self.invoice_number = 'INV000001'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} - {self.member.user.username}"
    
class Complaint(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='complaints')
    society = models.ForeignKey(Society, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    resolved_at = models.DateTimeField(null=True, blank=True)
    committee_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.created_by.user.username}"


class BillType(models.Model):
    society = models.ForeignKey(Society, on_delete=models.CASCADE)
    bill_number = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Member, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    qr_code = models.ImageField(upload_to='bill_qr_codes/', null=True, blank=True)  # Add this field
    due_date = models.DateField()  # New field
    status = models.CharField(max_length=20, choices=[('PAID', 'Paid'), ('PENDING', 'Pending')])

    @property
    def is_overdue(self):
        if self.due_date and self.status != 'PAID':
            return self.due_date < timezone.now().date()  # Convert timezone.now() to a date
        return False



