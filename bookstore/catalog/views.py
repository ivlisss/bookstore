import json
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Prefetch, Sum
from django.core.paginator import Paginator
from .models import Book, Category, Author, Order, OrderItem, Cart, CartItem
from .forms import LoginForm, RegisterForm, UserProfileForm, OrderForm, BookForm, CategoryForm, AuthorForm, PublisherForm
from django.contrib.auth.views import LoginView
from django.contrib.admin.models import LogEntry
from . serializers import *
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import timedelta


def home(request):
    # Новые книги
    new_books = Book.objects.order_by('-created_at')[:8]
    
    # Популярные книги (по количеству заказов)
    popular_books = Book.objects.annotate(
        order_count=Count('order_items')
    ).order_by('-order_count')[:8]
    
    # Категории с количеством книг
    categories = Category.objects.annotate(book_count=Count('books'))
    
    context = {
        'new_books': new_books,
        'popular_books': popular_books,
        'categories': categories,
    }
    return render(request, 'catalog/home.html', context)

def book_list(request):
    books = Book.objects.all()
    
    # Поиск
    query = request.GET.get('search')
    if query:
        # Базовый поиск (без учета регистра)
        books = books.filter(
            Q(title__icontains=query) | 
            Q(author__first_name__icontains=query) |
            Q(author__last_name__icontains=query)
        )
        # с учетом регистра
        if query and query[0].islower():
            query_capitalized = query.capitalize()
            books = books | Book.objects.filter(
                Q(title__icontains=query_capitalized) | 
                Q(author__first_name__icontains=query_capitalized) |
                Q(author__last_name__icontains=query_capitalized)
            )
    # Фильтрация по автору
    author_id = request.GET.get('author')
    if author_id:
        books = books.filter(author_id=author_id)
    
    # Фильтрация по цене
    min_price = request.GET.get('min_price')
    if min_price:
        books = books.filter(price__gte=min_price)
    
    max_price = request.GET.get('max_price')
    if max_price:
        books = books.filter(price__lte=max_price)
    
    # Пагинация
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.all()
    authors = Author.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'authors': authors,
        'search_query': query,
    }
    return render(request, 'catalog/book_list.html', context)

def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    related_books = Book.objects.filter(
        categories__in=book.categories.all()
    ).exclude(id=book.id).distinct()[:4]
    
    context = {
        'book': book,
        'related_books': related_books,
    }
    return render(request, 'catalog/book_detail.html', context)

def category_books(request, slug):
    category = get_object_or_404(Category, slug=slug)
    books = Book.objects.filter(categories=category)
    
    # Пагинация
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, 'catalog/category_books.html', context)

def register(request):
    if request.method == 'POST':
        form =RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            Cart.objects.create(user=request.user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('home')
    else:
        form = RegisterForm()
    
    return render(request, 'catalog/register.html', {'form': form})

class CustomLoginView(LoginView):
    template_name = 'catalog/login.html'
    authentication_form = LoginForm
    
    def form_valid(self, form):
        messages.success(self.request, f'Добро пожаловать, {form.get_user().username}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Ошибка входа. Проверьте правильность данных.')
        return super().form_invalid(form)

@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлен!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    cart = Cart.objects.filter(user=request.user)
    cartItems = cart[0].total_items
    
    context = {
        'form': form,
        'orders': orders,
        'cartItems': cartItems,
    }
    return render(request, 'catalog/profile.html', context)


from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Cart, CartItem, Book

@login_required
def cart_view(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
    
    if request.method == 'POST':
        # Обработка очистки корзины
        if 'clear_cart' in request.POST:
            cart.items.all().delete()
            messages.success(request, 'Корзина очищена')
            return redirect('cart')
        
        # Обработка добавления товара
        book_id = request.POST.get('book_id')
        quantity = int(request.POST.get('quantity', 1))
        
        if book_id:
            book = get_object_or_404(Book, id=book_id)
            cart.add_item(book, quantity)
            messages.success(request, f'Книга "{book.title}" добавлена в корзину!')
        
        return redirect('cart')
    
    context = {
        'cart': cart,
    }
    return render(request, 'catalog/cart.html', context)

@login_required
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            cart_item.delete()
            messages.success(request, 'Товар удален из корзины')
        else:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Количество обновлено')
    
    return redirect('cart')

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    messages.success(request, 'Товар удален из корзины')
    return redirect('cart')

@login_required
def checkout(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
    
    if cart.items.count() == 0:
        messages.error(request, 'Ваша корзина пуста')
        return redirect('cart')
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            delivery_method = request.POST.get('delivery_method', 'pickup')
            delivery_cost = 300 if delivery_method == 'delivery' else 0
            
            # Добавляем адрес доставки только для курьерской доставки
            if delivery_method == 'delivery':
                shipping_address = form.cleaned_data['shipping_address']
                if not shipping_address:
                    messages.error(request, 'Для курьерской доставки необходимо указать адрес')
                    return render(request, 'catalog/checkout.html', {
                        'form': form,
                        'cart': cart
                    })
            else:
                shipping_address = 'Самовывоз'
            
            # Создаем заказ
            order = Order.objects.create(
                user=request.user,
                delivery_method=delivery_method,
                delivery_cost=delivery_cost,
                total_price=cart.total_price() + delivery_cost,
                shipping_address=shipping_address,
                total_amount=cart.total_price() + delivery_cost
            )
            
            # Создаем позиции заказа
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    book=cart_item.book,
                    quantity=cart_item.quantity,
                    price=cart_item.book.price
                )
                
                # Обновляем количество на складе
                cart_item.book.stock_quantity -= cart_item.quantity
                cart_item.book.save()
            
            # Очищаем корзину
            cart.items.all().delete()
            
            messages.success(request, f'Заказ #{order.id} успешно создан!')
            return redirect('order_detail', order_id=order.id)
        else:
            # Если форма не валидна, показываем ошибки
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
    else:
        form = OrderForm()
    
    return render(request, 'catalog/checkout.html', {
        'form': form,
        'cart': cart
    })

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'catalog/order_detail.html', {'order': order})

@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'catalog/order_list.html', {'orders': orders})

# @require_POST # Разрешаем только POST-запросы
@login_required
def order_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status not in ['pending', 'processing']:
        messages.error(request, f'Невозможно отменить заказ №{order_id} в статусе "{order.get_status_display()}".')
        return redirect('order_detail', order_id=order.id)
    
    try:
        order.status = 'cancelled'
        order.save()
        
        messages.success(request, f'Заказ №{order_id} был успешно отменен.')
    
    except Exception as e:
        messages.error(request, f'Произошла ошибка при отмене заказа: {e}')
    
    return redirect('order_detail', order_id=order.id)

@login_required
def admin_access_required(request):
    if not request.user.is_admin():
        return HttpResponseForbidden("У вас нет прав доступа к админ-панели")
    return redirect('admin_statistics')


def is_admin(user):
    # user может быть AnonymousUser, поэтому проверяем сначала is_authenticated
    if hasattr(user, 'is_authenticated') and user.is_authenticated:
        return user.is_superuser or getattr(user, 'role', None) == 'admin'
    return False

def admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Проверяем, что пользователь либо superuser, либо имеет роль 'admin'
        if not (request.user.is_superuser or getattr(request.user, 'role', None) == 'admin'):
            return HttpResponseForbidden("У вас нет прав доступа к админ-панели")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_statistics(request):
    # Статистика за последние 30 дней
    thirty_days_ago = timezone.now() - timedelta(days=30)

    recent_actions = []
    log_entries = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:10]
    
    for action in log_entries:
        # Определяем тип действия
        action_types = {
            LogEntry.ADDITION: 'Добавлен',
            LogEntry.CHANGE: 'Изменен', 
            LogEntry.DELETION: 'Удален'
        }
        
        action_name = action_types.get(action.action_flag, 'Действие')
        object_name = str(action.object_repr)
        
        # Обрезаем длинное название
        if len(object_name) > 30:
            object_name = object_name[:27] + '...'
        
        # Форматируем действие
        formatted_action = f"{action_name} {action.content_type}: {object_name}"
        
        recent_actions.append({
            'user': action.user,
            'action_time': action.action_time,
            'formatted_action': formatted_action,
            'content_type': action.content_type.model,
            'action_flag': action.action_flag,
            'object_name': object_name
        })
    # Данные для графиков
    # График продаж по дням за последние 7 дней
    sales_data = []
    dates = []
    for i in range(6, -1, -1):
        date = timezone.now() - timedelta(days=i)
        daily_sales = Order.objects.filter(
            created_at__date=date.date(),
            status='delivered'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        sales_data.append(float(daily_sales))
        dates.append(date.strftime('%d.%m'))
    

    
    popular_categories = Category.objects.annotate(
        book_count=Count('books')
    ).order_by('-book_count')[:5]
    
    
    context = {
        'total_books': Book.objects.count(),
        'total_orders': Order.objects.count(),
        'total_users': User.objects.count(),
        'total_revenue': Order.objects.filter(status='delivered').aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        
        'recent_orders': Order.objects.filter(created_at__gte=thirty_days_ago).count(),
        'recent_revenue': Order.objects.filter(created_at__gte=thirty_days_ago, status='delivered')
                         .aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'new_users': User.objects.filter(date_joined__gte=thirty_days_ago).count(),
        
        'popular_books': Book.objects.annotate(order_count=Count('order_items'))
                       .order_by('-order_count')[:5],
        
        'order_stats': Order.objects.values('status').annotate(count=Count('id')),
        
        'latest_orders': Order.objects.select_related('user').order_by('-created_at')[:4],
        
        'low_stock_books': Book.objects.filter(stock_quantity__lt=10).order_by('stock_quantity')[:5],
        
        # Данные для графиков
        'sales_data': sales_data,
        'sales_dates': dates,
        'popular_categories': popular_categories,

        'recent_actions': recent_actions,
    }
    
    return render(request, 'admin/statistics.html', context)
@admin_required
def admin_books(request):
    books = Book.objects.select_related('author', 'publisher').prefetch_related('categories').all()
    
    # Фильтрация
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    author = request.GET.get('author', '')
    low_stock = request.GET.get('low_stock', '')
    
    if search:
        books = books.filter(Q(title__icontains=search) | Q(isbn__icontains=search))
    if search and search[0].islower():
            search_capitalized = search.capitalize()
            books = books | Book.objects.filter(Q(title__icontains=search_capitalized) | Q(isbn__icontains=search_capitalized))
    if category:
        books = books.filter(categories__id=category)
    if author:
        books = books.filter(author__id=author)
    if low_stock:
        books = books.filter(stock_quantity__lt=10)
    
    categories = Category.objects.all()
    authors = Author.objects.all()
    
    context = {
        'books': books,
        'categories': categories,
        'authors': authors,
        'search_query': search,
        'selected_category': category,
        'selected_author': author,
        'show_low_stock': low_stock,
    }
    
    return render(request, 'admin/books.html', context)

@admin_required
def admin_book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, 'Книга успешно обновлена!')
            return redirect('admin_books')
    else:
        form = BookForm(instance=book)
    
    context = {
        'book': book,
        'form': form,
    }
    
    return render(request, 'admin/book_detail.html', context)

@admin_required
def admin_book_create(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Книга успешно создана!')
            return redirect('admin_books')
    else:
        form = BookForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'admin/book_create.html', context)

@admin_required
def admin_book_delete(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        book.delete()
        messages.success(request, 'Книга успешно удалена!')
        return redirect('admin_books')
    
    context = {
        'book': book,
    }
    
    return render(request, 'admin/book_delete.html', context)

@admin_required
def admin_orders(request):
    orders = Order.objects.select_related('user').prefetch_related('items').all()
    
    # Фильтрация
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    if status:
        orders = orders.filter(status=status)
    if search:
        orders = orders.filter(
            Q(user__username__icontains=search) | 
            Q(user__email__icontains=search) |
            Q(id__icontains=search)
        )
    
    context = {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'selected_status': status,
        'search_query': search,
    }
    
    return render(request, 'admin/orders.html', context)

@admin_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            messages.success(request, 'Статус заказа обновлен!')
            return redirect('admin_order_detail', order_id=order_id)
    
    context = {
        'order': order,
        'status_choices': Order.STATUS_CHOICES,
    }
    
    return render(request, 'admin/order_detail.html', context)

@admin_required
def admin_users(request):
    users = User.objects.all()
    
    # Фильтрация
    role = request.GET.get('role', '')
    search = request.GET.get('search', '')
    
    if role:
        users = users.filter(role=role)
    if search:
        users = users.filter(
            Q(username__icontains=search) | 
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    context = {
        'users': users,
        'role_choices': User.ROLE_CHOICES,
        'selected_role': role,
        'search_query': search,
    }
    
    return render(request, 'admin/users.html', context)

@admin_required
def admin_categories(request):
    categories = Category.objects.annotate(book_count=Count('books'))
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Категория создана!')
            return redirect('admin_categories')
    else:
        form = CategoryForm()
    
    context = {
        'categories': categories,
        'form': form,
    }
    
    return render(request, 'admin/categories.html', context)

@admin_required
def admin_category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Категория удалена!')
        return redirect('admin_categories')
    
    context = {
        'category': category,
    }
    
    return render(request, 'admin/category_delete.html', context)

@admin_required
def admin_authors(request):
    if request.method == 'POST':
        if 'edit_author' in request.POST:
            # Редактирование существующего автора
            author_id = request.POST.get('author_id')
            author = get_object_or_404(Author, id=author_id)
            author.first_name = request.POST.get('first_name')
            author.last_name = request.POST.get('last_name')
            author.birth_date = request.POST.get('birth_date')
            author.website = request.POST.get('website')
            author.bio = request.POST.get('bio')
            author.save()
            messages.success(request, 'Автор обновлен!')
            
        elif 'add_author' in request.POST:
            # Добавление нового автора
            Author.objects.create(
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                birth_date=request.POST.get('birth_date'),
                website=request.POST.get('website'),
                bio=request.POST.get('bio')
            )
            messages.success(request, 'Автор добавлен!')
        
        return redirect('admin_authors')
    
    # GET запрос - показать список авторов
    authors = Author.objects.annotate(book_count=Count('books'))
    context = {'authors': authors}
    return render(request, 'admin/authors.html', context)

@admin_required
def admin_author_delete(request, author_id):
    author = get_object_or_404(Author, id=author_id)
    
    if request.method == 'POST':
        # Проверяем, есть ли у автора книги
        if author.books.exists():
            messages.error(request, 'Нельзя удалить автора, у которого есть книги!')
            return redirect('admin_authors')
        
        author.delete()
        messages.success(request, 'Автор удален!')
        return redirect('admin_authors')
    
    # Аннотируем количество книг для отображения в шаблоне
    author.book_count = author.books.count()
    
    context = {
        'author': author,
    }
    return render(request, 'admin/author_delete.html', context)

@admin_required
def admin_publishers(request):
    if request.method == 'POST':
        if 'edit_publisher' in request.POST:
            # Редактирование существующего издательства
            publisher_id = request.POST.get('publisher_id')
            publisher = get_object_or_404(Publisher, id=publisher_id)
            publisher.name = request.POST.get('name')
            publisher.address = request.POST.get('address')
            publisher.website = request.POST.get('website')
            publisher.save()
            messages.success(request, 'Издательство обновлено!')
            
        elif 'add_publisher' in request.POST:
            # Добавление нового издательства
            Publisher.objects.create(
                name=request.POST.get('name'),
                address=request.POST.get('address'),
                website=request.POST.get('website')
            )
            messages.success(request, 'Издательство добавлено!')
        
        return redirect('admin_publishers')
    
    # GET запрос - показать список издательств
    publishers = Publisher.objects.annotate(book_count=Count('books'))
    context = {'publishers': publishers}
    return render(request, 'admin/publishers.html', context)

@admin_required
def admin_publisher_delete(request, publisher_id):
    publisher = get_object_or_404(Publisher, id=publisher_id)
    publisher.book_count = publisher.books.count()
    
    if request.method == 'POST':
        if publisher.book_count > 0:
            messages.error(request, 'Нельзя удалить издательство с книгами!')
            return redirect('admin_publishers')
        publisher.delete()
        messages.success(request, 'Издательство удалено!')
        return redirect('admin_publishers')
    
    return render(request, 'admin/publisher_delete.html', {'publisher': publisher})


# API
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        logout(request)
        Token.objects.filter(user=request.user).delete()
        return Response({'detail': 'Successfully logged out'})

class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        Cart.objects.get_or_create(user=user)
        token = Token.objects.create(user=user)
        
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    

class BookListView(generics.ListCreateAPIView):
    queryset = Book.objects.select_related('author', 'publisher').prefetch_related('categories')
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(categories__id=category)
        
        author = self.request.GET.get('author')
        if author:
            queryset = queryset.filter(author__id=author)
        
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        sort_by = self.request.GET.get('sort', 'title')
        if sort_by in ['title', 'price', 'created_at', '-price', '-created_at']:
            queryset = queryset.order_by(sort_by)
        
        return queryset

class BookDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Book.objects.select_related('author', 'publisher').prefetch_related('categories')
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# Category Views
class CategoryListView(generics.ListCreateAPIView):
    queryset = Category.objects.annotate(books_count=Count('books'))
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.annotate(books_count=Count('books'))
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# Author Views
class AuthorListView(generics.ListCreateAPIView):
    queryset = Author.objects.annotate(books_count=Count('books'))
    serializer_class = AuthorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class AuthorDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Author.objects.annotate(books_count=Count('books'))
    serializer_class = AuthorSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# Publisher Views
class PublisherListView(generics.ListCreateAPIView):
    queryset = Publisher.objects.annotate(books_count=Count('books'))
    serializer_class = PublisherSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class PublisherDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Publisher.objects.annotate(books_count=Count('books'))
    serializer_class = PublisherSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# Cart Views - используем ViewSet для кастомных действий
class CartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        """Получить корзину текущего пользователя"""
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Получить корзину по ID (для текущего пользователя)"""
        cart = get_object_or_404(Cart, id=pk, user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def add_item(self, request):
        """Добавить товар в корзину"""
        cart, created = Cart.objects.get_or_create(user=request.user)
        book_id = request.data.get('book_id')
        quantity = int(request.data.get('quantity', 1))
        
        try:
            book = Book.objects.get(id=book_id)
            if book.stock_quantity < quantity:
                return Response(
                    {'error': 'Недостаточно товара на складе'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart, 
                book=book,
                defaults={'quantity': quantity}
            )
            
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            
            serializer = CartSerializer(cart)
            return Response(serializer.data)
            
        except Book.DoesNotExist:
            return Response(
                {'error': 'Книга не найдена'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def update_item(self, request):
        """Обновить количество товара в корзине"""
        cart = get_object_or_404(Cart, user=request.user)
        book_id = request.data.get('book_id')
        quantity = int(request.data.get('quantity', 1))
        
        try:
            cart_item = CartItem.objects.get(cart=cart, book_id=book_id)
            if quantity <= 0:
                cart_item.delete()
            else:
                cart_item.quantity = quantity
                cart_item.save()
            
            serializer = CartSerializer(cart)
            return Response(serializer.data)
            
        except CartItem.DoesNotExist:
            return Response(
                {'error': 'Товар не найден в корзине'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def remove_item(self, request):
        """Удалить товар из корзины"""
        cart = get_object_or_404(Cart, user=request.user)
        book_id = request.data.get('book_id')
        
        try:
            cart_item = CartItem.objects.get(cart=cart, book_id=book_id)
            cart_item.delete()
            
            serializer = CartSerializer(cart)
            return Response(serializer.data)
            
        except CartItem.DoesNotExist:
            return Response(
                {'error': 'Товар не найден в корзине'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Очистить корзину"""
        cart = get_object_or_404(Cart, user=request.user)
        cart.items.all().delete()
        
        serializer = CartSerializer(cart)
        return Response(serializer.data)

# Order Views
class OrderListView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('book'))
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        cart = get_object_or_404(Cart, user=self.request.user)
        
        if cart.items.count() == 0:
            raise serializers.ValidationError("Корзина пуста")
        
        # Проверяем наличие товаров
        for item in cart.items.all():
            if item.book.stock_quantity < item.quantity:
                raise serializers.ValidationError(
                    f"Недостаточно товара: {item.book.title}"
                )
        
        # Создаем заказ
        order = serializer.save(
            user=self.request.user,
            total_amount=cart.total_price
        )
        
        # Создаем позиции заказа и обновляем склад
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                book=cart_item.book,
                quantity=cart_item.quantity,
                price=cart_item.book.price
            )
            # Обновляем склад
            cart_item.book.stock_quantity -= cart_item.quantity
            cart_item.book.save()
        
        # Очищаем корзину
        cart.items.all().delete()

class OrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('book'))
        )

# поиск
class SearchAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        query = request.GET.get('q', '')
        
        if not query:
            return Response({'error': 'Query parameter "q" is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        books = Book.objects.filter(
            Q(title__icontains=query) |
            Q(author__first_name__icontains=query) |
            Q(author__last_name__icontains=query) |
            Q(description__icontains=query)
        )[:20]
        
        serializer = BookSerializer(books, many=True)
        return Response({
            'query': query,
            'results': serializer.data,
            'count': books.count()
        })