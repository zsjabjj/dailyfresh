from django.conf.urls import url
from cart import views


urlpatterns = [
    # 添加购物车
    url(r'^add$', views.AddCartView.as_view(), name='add'),
    # 购物车列表
    url(r'^$', views.CartInfoView.as_view(), name='info'),
    # 编辑商品数量
    url(r'^update$', views.UpdateCartView.as_view(), name='update'),
    # 删除
    url(r'^delete$', views.DeleteCartView.as_view(), name='delete'),

]