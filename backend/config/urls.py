from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import FileResponse, HttpResponse
import os

def serve_react(request, path=''):
    """Serve React build files, fallback to index.html for SPA routing."""
    dist_dir = os.path.join(settings.BASE_DIR, '..', 'frontend', 'dist')
    
    # Try to serve exact static file
    if path:
        file_path = os.path.join(dist_dir, path)
        if os.path.isfile(file_path):
            return FileResponse(open(file_path, 'rb'))
    
    # Fallback to index.html for SPA
    index_path = os.path.join(dist_dir, 'index.html')
    if os.path.isfile(index_path):
        with open(index_path, 'r') as f:
            return HttpResponse(f.read(), content_type='text/html')
    
    return HttpResponse('Frontend not built. Run: cd frontend && npm run build', status=404)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('kyc.urls')),
    # Serve frontend assets
    re_path(r'^assets/(?P<path>.*)$', serve_react),
    # SPA catch-all
    re_path(r'^(?!api|admin|media|static).*$', serve_react),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
