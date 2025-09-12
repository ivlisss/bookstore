import json
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import Book, Category, Author, Order, OrderItem, Cart, CartItem
from .forms import LoginForm, RegisterForm, UserProfileForm, OrderForm
from django.contrib.auth.views import LoginView
from django.contrib.admin.models import LogEntry

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
    
    # Фильтрация
    category_slug = request.GET.get('category')
    author_id = request.GET.get('author')
    search_query = request.GET.get('search')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    
    if category_slug:
        books = books.filter(categories__slug=category_slug)
    if author_id:
        books = books.filter(author_id=author_id)
    if search_query:
        books = books.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(author__first_name__icontains=search_query) |
            Q(author__last_name__icontains=search_query)
        )
    if min_price:
        books = books.filter(price__gte=min_price)
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
        'search_query': search_query,
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
    
    context = {
        'form': form,
        'orders': orders,
    }
    return render(request, 'catalog/profile.html', context)


@login_required
def cart_view(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
    
    if request.method == 'POST':
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
        messages.error(request, 'Ваша корзина пуста')
        return redirect('cart')
    
    if cart.items.count() == 0:
        messages.error(request, 'Ваша корзина пуста')
        return redirect('cart')
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Создаем заказ
            order = Order.objects.create(
                user=request.user,
                shipping_address=form.cleaned_data['shipping_address'],
                total_amount=cart.total_price
            )
            
            # Добавляем товары из корзины в заказ
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    book=cart_item.book,
                    quantity=cart_item.quantity,
                    price=cart_item.book.price
                )
            
            # Очищаем корзину
            cart.clear()
            
            messages.success(request, f'Заказ #{order.id} успешно создан!')
            return redirect('order_detail', order_id=order.id)
    else:
        # Предзаполняем адрес доставки из профиля
        initial = {'shipping_address': request.user.get_full_address()}
        form = OrderForm(initial=initial)
    
    context = {
        'cart': cart,
        'form': form,
    }
    return render(request, 'catalog/checkout.html', context)

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
    # Получаем заказ или возвращаем 404
    # Важно: фильтруем по текущему пользователю, чтобы нельзя было отменить чужой заказ!
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Проверяем, можно ли отменить заказ (например, только из определенных статусов)
    if order.status not in ['pending', 'processing']:
        messages.error(request, f'Невозможно отменить заказ №{order_id} в статусе "{order.get_status_display()}".')
        return redirect('order_detail', order_id=order.id)
    
    # Логика отмены
    try:
        # Меняем статус заказа
        order.status = 'cancelled'
        order.save()
        
        # Здесь можно добавить другую логику, например:
        # - Отправить email уведомление
        # - Вернуть товары на склад (увеличить stock)
        # - Инициировать возврат денег через платежную систему
        
        messages.success(request, f'Заказ №{order_id} был успешно отменен.')
    
    except Exception as e:
        # Ловим возможные ошибки при сохранении
        messages.error(request, f'Произошла ошибка при отмене заказа: {e}')
    
    # Перенаправляем обратно на страницу деталей заказа
    return redirect('order_detail', order_id=order.id)

@login_required
def admin_access_required(request):
    if not request.user.is_admin():
        return HttpResponseForbidden("У вас нет прав доступа к админ-панели")
    return redirect('admin_dashboard')

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import User, Book, Category, Author, Publisher, Order
from .forms import BookForm, CategoryForm, AuthorForm, PublisherForm

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

def admin_dashboard(request):
    # Статистика за последние 30 дней
    thirty_days_ago = timezone.now() - timedelta(days=30)

    recent_actions = []
    log_entries = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:10]
    
    for action in log_entries:
        action_dict = {
            LogEntry.ADDITION: 'Добавлен',
            LogEntry.CHANGE: 'Изменен',
            LogEntry.DELETION: 'Удален'
        }
        
        action_name = action_dict.get(action.action_flag, 'Действие')
        object_name = str(action.object_repr)
        
        if len(object_name) > 30:
            object_name = object_name[:27] + '...'
        
        formatted_action = f"{action_name} {action.content_type}: {object_name}"
        
        recent_actions.append({
            'user': action.user,
            'action_time': action.action_time,
            'formatted_action': formatted_action,
            'content_type': action.content_type.model,
            'action_flag': action.action_flag
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
    
    
    # График популярных категорий
    category_data = []
    category_labels = []
    category_colors = ['#ff6384', '#36a2eb', '#ffcd56', '#4bc0c0', '#9966ff', '#ff9f40', '#c9cbcf']
    
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
        
        'latest_orders': Order.objects.select_related('user').order_by('-created_at')[:10],
        
        'low_stock_books': Book.objects.filter(stock_quantity__lt=10).order_by('stock_quantity')[:5],
        
        # Данные для графиков
        'sales_data': sales_data,
        'sales_dates': dates,
        'popular_categories': popular_categories,

        'recent_actions': recent_actions,
    }
    
    return render(request, 'admin/dashboard.html', context)
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
    authors = Author.objects.annotate(book_count=Count('books'))
    
    if request.method == 'POST':
        form = AuthorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Автор создан!')
            return redirect('admin_authors')
    else:
        form = AuthorForm()
    
    context = {
        'authors': authors,
        'form': form,
    }
    
    return render(request, 'admin/authors.html', context)

@admin_required
def admin_publishers(request):
    publishers = Publisher.objects.annotate(book_count=Count('books'))
    
    if request.method == 'POST':
        form = PublisherForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Издательство создано!')
            return redirect('admin_publishers')
    else:
        form = PublisherForm()
    
    context = {
        'publishers': publishers,
        'form': form,
    }
    
    return render(request, 'admin/publishers.html', context)