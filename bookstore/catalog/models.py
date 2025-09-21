from django.conf import settings
from django.db import models  # Для использования встроенной модели User, если нужно
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.utils import timezone
import datetime
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Администратор'),
        ('user', 'Пользователь'),
    )
    
    role = models.CharField(
        max_length=10, 
        choices=ROLE_CHOICES, 
        default='user',
        verbose_name='Роль'
    )
    
    phone = models.CharField(
        max_length=15, 
        blank=True, 
        verbose_name='Телефон'
    )
    
    address = models.TextField(
        blank=True, 
        verbose_name='Адрес'
    )
    
    city = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name='Город'
    )
    
    postal_code = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name='Почтовый индекс'
    )
    
    country = models.CharField(
        max_length=100, 
        blank=True, 
        default='Россия',
        verbose_name='Страна'
    )
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
    
    def __str__(self):
        return self.username
    
    def is_admin(self):
        return self.role == 'admin' or self.role == 'admin'
    
    def get_full_address(self):
        """Возвращает полный адрес в формате строки"""
        parts = []
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country)
        if self.city:
            parts.append(f"г. {self.city}")
        if self.address:
            parts.append(self.address)
        return ", ".join(parts) if parts else "Адрес не указан"

# 1. Категории книг
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название категории")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="URL категории")
    description = models.TextField(blank=True, verbose_name="Описание категории")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['name']

    def __str__(self):
        return self.name

# 2. Авторы книг
class Author(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    bio = models.TextField(blank=True, verbose_name="Биография")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    website = models.URLField(blank=True, verbose_name="Веб-сайт")

    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

# 3. Издательства
class Publisher(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название издательства")
    address = models.CharField(max_length=255, blank=True, verbose_name="Адрес")
    website = models.URLField(blank=True, verbose_name="Веб-сайт")

    class Meta:
        verbose_name = "Издательство"
        verbose_name_plural = "Издательства"
        ordering = ['name']

    def __str__(self):
        return self.name

# 4. Книги
class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="URL книги")
    author = models.ForeignKey(Author, related_name='books', on_delete=models.SET_NULL, verbose_name="Автор", null=True)
    publisher = models.ForeignKey(Publisher, related_name='books', on_delete=models.SET_NULL, verbose_name="Издательство", null=True)
    categories = models.ManyToManyField(Category, related_name='books', verbose_name="Категории")
    isbn = models.CharField(max_length=13, unique=True, verbose_name="ISBN") # ISBN-13
    description = models.TextField(blank=True, verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена")
    stock_quantity = models.PositiveIntegerField(verbose_name="Количество на складе")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления записи")
    image = models.ImageField(upload_to='images/', help_text="Добавьте изображение обложки", null=True, blank=True)

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ['title']

    def __str__(self):
        return self.title

# 8. Заказы
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('processing', 'Обработка'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменен'),
    ]
    DELIVERY_CHOICES = [
        ('pickup', 'Самовывоз'),
        ('delivery', 'Курьерская доставка'),
    ]
    user = models.ForeignKey(User, related_name='orders', on_delete=models.CASCADE, verbose_name="Покупатель")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата заказа")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Общая сумма", null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус заказа")
    shipping_address = models.TextField(verbose_name="Адрес доставки")
    delivery_method = models.CharField(
        max_length=10,
        choices=DELIVERY_CHOICES,
        default='pickup',
        verbose_name='Способ доставки'
    )
    delivery_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Стоимость доставки'
    )
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='Общая стоимость',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} for {self.customer.user.username} ({self.status})"

# 9. Позиции в заказе
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, verbose_name="Заказ")
    book = models.ForeignKey(Book, related_name='order_items', on_delete=models.CASCADE, verbose_name="Книга")
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена за единицу") # Цена на момент заказа

    class Meta:
        verbose_name = "Позиция в заказе"
        verbose_name_plural = "Позиции в заказе"
        ordering = ['order', 'book']

    def __str__(self):
        return f"{self.quantity} x {self.book.title} in Order #{self.order.id}"

    def get_total_price(self):
        return self.quantity * self.price
    

class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        verbose_name='Пользователь'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        return f'Корзина пользователя {self.user.username}'

    @property
    def total_items(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def total_price(self):
        """Возвращает общую стоимость товаров в корзине"""
        total = 0
        for item in self.items.all():
            total += item.total_price()
        return total

    def add_item(self, book, quantity=1):
        """Добавить товар в корзину"""
        cart_item, created = CartItem.objects.get_or_create(
            cart=self,
            book=book,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        return cart_item

    def remove_item(self, book):
        """Удалить товар из корзины"""
        try:
            cart_item = CartItem.objects.get(cart=self, book=book)
            cart_item.delete()
            return True
        except CartItem.DoesNotExist:
            return False

    def update_item_quantity(self, book, quantity):
        """Обновить количество товара"""
        try:
            cart_item = CartItem.objects.get(cart=self, book=book)
            if quantity <= 0:
                cart_item.delete()
            else:
                cart_item.quantity = quantity
                cart_item.save()
            return True
        except CartItem.DoesNotExist:
            return False

    def clear(self):
        """Очистить корзину"""
        self.items.all().delete()

class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Корзина'
    )
    book = models.ForeignKey(
        'Book',
        on_delete=models.CASCADE,
        verbose_name='Книга'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')

    class Meta:
        verbose_name = 'Элемент корзины'
        verbose_name_plural = 'Элементы корзины'
        unique_together = ['cart', 'book']

    def __str__(self):
        return f'{self.quantity} x {self.book.title}'

    def total_price(self):
        return self.quantity * self.book.price