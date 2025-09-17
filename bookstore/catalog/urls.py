from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'cart', views.CartViewSet, basename='cart')

urlpatterns = [
    path('api/', include(router.urls)),
    # Публичные маршруты
    path('', views.home, name='home'),
    path('books/', views.book_list, name='book_list'),
    path('books/<int:book_id>/', views.book_detail, name='book_detail'),
    path('category/<slug:slug>/', views.category_books, name='category_books'),
    
    # Аутентификация
    path('register/', views.register, name='register'),
    path('login/', views.CustomLoginView.as_view(template_name='catalog/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Пользовательские маршруты
    path('profile/', views.profile, name='profile'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/cancel/', views.order_cancel, name='order_cancel'),
    
    # Админ-маршруты
    path('admin/', views.admin_access_required, name='admin_redirect'),
    path('admin/statistics/', views.admin_statistics, name='admin_statistics'),
    path('admin/books/', views.admin_books, name='admin_books'),
    path('admin/books/create/', views.admin_book_create, name='admin_book_create'),
    path('admin/books/<int:book_id>/', views.admin_book_detail, name='admin_book_detail'),
    path('admin/books/<int:book_id>/delete/', views.admin_book_delete, name='admin_book_delete'),
    path('admin/orders/', views.admin_orders, name='admin_orders'),
    path('admin/orders/<int:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/categories/', views.admin_categories, name='admin_categories'),
    path('admin/categories/<int:category_id>/delete/', views.admin_category_delete, name='admin_category_delete'),
    path('admin/authors/', views.admin_authors, name='admin_authors'),
    path('admin/publishers/', views.admin_publishers, name='admin_publishers'),

    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt',
             success_url='/password-reset/done/'
         ), 
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ), 
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/password-reset-complete/'
         ), 
         name='password_reset_confirm'),
    
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ), 
         name='password_reset_complete'),

    path('api/register/', views.RegisterView.as_view(), name='api_register'),
    path('api/login/', views.LoginView.as_view(), name='api_login'),
    path('api/logout/', views.LogoutView.as_view(), name='api_logout'),
    
    # Books
    path('api/books/', views.BookListView.as_view(), name='book-list'),
    path('api/books/<int:pk>/', views.BookDetailView.as_view(), name='book-detail'),
    
    # Categories
    path('api/categories/', views.CategoryListView.as_view(), name='category-list'),
    path('api/categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    
    # Authors
    path('api/authors/', views.AuthorListView.as_view(), name='author-list'),
    path('api/authors/<int:pk>/', views.AuthorDetailView.as_view(), name='author-detail'),
    
    # Publishers
    path('api/publishers/', views.PublisherListView.as_view(), name='publisher-list'),
    path('api/publishers/<int:pk>/', views.PublisherDetailView.as_view(), name='publisher-detail'),
    
    # Orders
    path('api/orders/', views.OrderListView.as_view(), name='order-list'),
    path('api/orders/<int:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    
    # Search
    path('api/search/', views.SearchAPIView.as_view(), name='search'),
]
