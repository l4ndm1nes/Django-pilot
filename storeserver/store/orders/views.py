import http
import json
from http import HTTPStatus

import stripe
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

from common.views import TitleMixin
from orders.forms import OrderForm
from orders.models import Order
from products.models import Basket

stripe.api_key = settings.STRIPE_SECRET_KEY

# Create your views here.
class SuccessTemplateView(TitleMixin, TemplateView):
    template_name = 'orders/success.html'
    title = 'Спасибо за заказ!'

class CancelTemplateView(TitleMixin, TemplateView):
    template_name = 'orders/cancel.html'

class OrderListView(TitleMixin, ListView):
    template_name = 'orders/orders.html'
    title = 'Store - Заказы'
    queryset = Order.objects.all()
    ordering = '-created'

    def get_queryset(self):
        queryset = super(OrderListView, self).get_queryset()
        return queryset.filter(initiator=self.request.user)

class OrderDetailView(DetailView):
    template_name = 'orders/order.html'
    model = Order

    def get_context_data(self, **kwargs):
        context = super(OrderDetailView, self).get_context_data(**kwargs)
        context['title'] = f'Store - Заказ №{self.object.id}'
        return context

class OrderCreateView(TitleMixin, CreateView):
    template_name = 'orders/order-create.html'
    form_class = OrderForm
    success_url = reverse_lazy('orders:order-create')
    title = 'Store - Оформление заказа'

    def post(self, request, *args, **kwargs):
        super(OrderCreateView, self).post(request, *args, **kwargs)
        baskets = Basket.objects.filter(user=self.request.user)

        checkout_session = stripe.checkout.Session.create(
            line_items=baskets.stripe_products(),
            metadata={'order_id': self.object.id},
            mode='payment',
            success_url='{}{}'.format(settings.DOMAIN_NAME, reverse('orders:order-success')),
            cancel_url='{}{}'.format(settings.DOMAIN_NAME, reverse('orders:order-cancel')),
        )

        return HttpResponseRedirect(checkout_session.url, http.HTTPStatus.SEE_OTHER)

    def form_valid(self, form):
        form.instance.initiator = self.request.user
        return super(OrderCreateView, self).form_valid(form)

@csrf_exempt
def stripe_webhook_view(request):
    print("Webhook received")  # Логирование получения вебхука
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        print(f'Event received: {event}')  # Логирование события
    except ValueError as e:
        # Неверный формат payload
        print('Error parsing payload: {}'.format(e))
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Неверная подпись
        print('Error verifying webhook signature: {}'.format(e))
        return HttpResponse(status=400)

    # Обработка события
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']  # содержит объект stripe.PaymentIntent
        handle_payment_intent_succeeded(payment_intent)
    elif event['type'] == 'payment_method.attached':
        payment_method = event['data']['object']  # содержит объект stripe.PaymentMethod
        handle_payment_method_attached(payment_method)
    elif event['type'] == 'checkout.session.completed':
        session = event['data']['object']  # содержит объект stripe.Checkout.Session
        handle_checkout_session_completed(session)
    elif event['type'] == 'charge.succeeded':
        charge = event['data']['object']  # содержит объект stripe.Charge
        handle_charge_succeeded(charge)
    elif event['type'] == 'charge.updated':
        charge = event['data']['object']  # содержит объект stripe.Charge
        handle_charge_updated(charge)
    elif event['type'] == 'payment_intent.created':
        payment_intent = event['data']['object']  # содержит объект stripe.PaymentIntent
        handle_payment_intent_created(payment_intent)
    else:
        print(f'Unhandled event type {event["type"]}')

    return HttpResponse(status=200)

def handle_payment_intent_succeeded(payment_intent):
    # Логика обработки успешного платежа
    print(f'PaymentIntent was successful: {payment_intent["id"]}')
    # Например, можно обновить статус заказа в базе данных

def handle_payment_method_attached(payment_method):
    # Логика обработки успешного присоединения метода оплаты
    print(f'PaymentMethod was attached to a Customer: {payment_method["id"]}')

def handle_checkout_session_completed(session):
    # Логика выполнения заказа без использования order_id
    print(f'Checkout session completed: {session["id"]}')
    fulfill_order(session)

def handle_charge_succeeded(charge):
    # Логика обработки успешного завершения платежа
    print(f'Charge was successful: {charge["id"]}')
    # Например, можно обновить статус заказа в базе данных

def handle_charge_updated(charge):
    # Логика обработки обновления платежа
    print(f'Charge was updated: {charge["id"]}')
    # Например, можно обновить информацию о платеже в базе данных

def handle_payment_intent_created(payment_intent):
    # Логика обработки создания платежного намерения
    print(f'PaymentIntent was created: {payment_intent["id"]}')
    # Например, можно создать запись о новом платежном намерении в базе данных

def fulfill_order(session):
    # Логика выполнения заказа
    order_id = int(session.metadata['order_id'])
    order = Order.objects.get(id=order_id)
    order.update_after_payment()
    print(f'Fulfilling order for session: {session["id"]}')
    # Обновите статус заказа в базе данных
    # Отправьте уведомление клиенту
    # Начните процесс доставки