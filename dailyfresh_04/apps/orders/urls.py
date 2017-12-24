from django.conf.urls import url
from orders import views



urlpatterns = [
    # 确认订单
    url(r'^place$', views.PlaceOrderView.as_view(), name='place'),
    # 提交订单
    url(r'^commit$', views.CommitOrderView.as_view(), name='commit'),
    # 展示订单详情
    url(r'^(?P<page>\d+)$', views.UserOrdersView.as_view(), name='info'),
    # 待支付
    url(r'^pay$', views.PayView.as_view(), name='pay'),
    # 查询订单信息
    url(r'^checkpay$', views.CheckPayView.as_view(), name='check'),
    # 评论
    url(r'^comment/(?P<order_id>\d+)$', views.CommentOrderView.as_view(), name='comment')

]