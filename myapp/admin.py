# admin.py
from django.contrib import admin
from .models import Society, Member, Announcement

# Register your models here.
class MemberInline(admin.TabularInline):
    model = Member
    extra = 0

class SocietyAdmin(admin.ModelAdmin):
    inlines = [MemberInline]

class MemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'society','building', 'flat_number', 'member_type', 'joined_at')
    list_filter = ('society', 'member_type')

# Customize the Announcement admin view
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'society', 'created_by', 'created_at')
    list_filter = ('society', 'created_at')
    search_fields = ('title', 'content')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    #undo here
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            member = Member.objects.get(user=request.user)
            return qs.filter(society=member.society)
        except Member.DoesNotExist:
            return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "society" and not request.user.is_superuser:
            try:
                member = Member.objects.get(user=request.user)
                kwargs["queryset"] = Society.objects.filter(id=member.society.id)
            except Member.DoesNotExist:
                kwargs["queryset"] = Society.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

admin.site.register(Society, SocietyAdmin)
admin.site.register(Member, MemberAdmin)
admin.site.register(Announcement, AnnouncementAdmin)

