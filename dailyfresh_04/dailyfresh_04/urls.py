"""dailyfresh_04 URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
from django.contrib import admin
import tinymce.urls
import haystack.urls

urlpatterns = [
    # 正则匹配，客户端的请求地址是否是'admin/'后台站点，如果是，就把后台站点中的url信息包含到项目中
    url(r'^admin/', include(admin.site.urls)),
    # haystack
    url(r'^search/', include(haystack.urls)),
    # 富文本编辑器
    url(r'^tinymce/', include(tinymce.urls)),
    # 如果正则匹配成功，表示服务器已经知道用户访问的是用户模块
    url(r'^users/', include('users.urls', namespace='users')),
    # 商品模块
    url(r'^', include('goods.urls', namespace='goods')),
    # 购物车
    url(r'^cart/', include('cart.urls', namespace='cart')),
    # 订单
    url(r'^orders/', include('orders.urls', namespace='orders'))
]
