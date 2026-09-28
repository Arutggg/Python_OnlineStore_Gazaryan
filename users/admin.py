from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from users.models import Address, User


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [AddressInline]
    list_display = ('username', 'last_name', 'first_name', 'middle_name', 'email', 'phone', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('middle_name', 'phone')}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'is_default')
    search_fields = ('city', 'street', 'user__username', 'user__last_name')
