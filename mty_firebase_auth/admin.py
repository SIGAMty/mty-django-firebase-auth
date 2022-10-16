from django.contrib import admin
from .models import FirebaseUser, FirebaseUserProvider

# Register your models here.

admin.site.register(FirebaseUser)
admin.site.register(FirebaseUserProvider)
