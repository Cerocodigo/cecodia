from django.contrib import admin
from django.urls import path, include
from core.views import home, signup


urlpatterns = [
    path('admin/', admin.site.urls),
    path('signup/', signup, name='signup'),
    path('', include('django.contrib.auth.urls')),
    path("", home, name="home"),
    path("", include("core.urls")),
]