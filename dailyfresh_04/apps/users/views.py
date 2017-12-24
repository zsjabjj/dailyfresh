from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.generic import View
from django.core.urlresolvers import reverse
import re
from users.models import User, Address
from django.db import IntegrityError
from celery_tasks.tasks import send_active_email
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from django.contrib.auth import authenticate, login, logout
from utils.views import LoginRequiredMixin
from django_redis import get_redis_connection
from goods.models import GoodsSKU
import json


# Create your views here.


class UserInfoView(LoginRequiredMixin, View):
    """用户中心之个人信息"""

    def get(self, request):
        """查询用户信息和地址信息，并展示"""

        # 获取哦用户
        user = request.user

        # 查询地址信息:查询用户所有地址信息
        # latest 按照时间排序，排序后获取最新的记录
        try:
            address = user.address_set.latest('create_time')
        except Address.DoesNotExist:
            address = None

        # 查询用户浏览记录信息：存储在redis中，以列表形式存储，存储sku_id, "history_userid: [0,1,2,3,4,5]"
        redis_conn = get_redis_connection("default")
        # 查询redis数据库中的浏览记录,查询最新的五条,将来保存记录时记得从左向右保存
        sku_ids = redis_conn.lrange('history_%s'%user.id, 0, 4)
        # 遍历sku_ids，分别取出每个sku_id,然后根据sku_id查询商品sku信息
        skuList = []
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            # 保存遍历出来的sku信息，存放在列表中
            skuList.append(sku)

        # 构造上下文: user在render()函数中，已经传入，不需要封装在上下文
        context = {'address': address, 'skuList':skuList}

        # 渲染模板
        return render(request, 'user_center_info.html', context)


class AddressView(LoginRequiredMixin, View):
    """用户中心之用户地址"""

    def get(self, request):
        """提供界面：查询用户地址，并展示"""

        # 获取用户，必须要先知道即将查询的地址是哪个用户的
        # 能够执行到这里，说明LoginRequiredMixin验证通过
        user = request.user

        # 查询地址信息:查询用户所有地址信息
        # address = Address.objects.filter(user=user).order_by('create_time')[0]
        # address = user.address_set.order_by('create_time')[0]
        # latest 按照时间排序，排序后获取最新的记录
        # id=1 create_time=9 北京市
        # id=2 create_time=10 上海市
        try:
            address = user.address_set.latest('create_time')
        except Address.DoesNotExist:
            address = None

        # 构造上下文: user在render()函数中，已经传入，不需要封装在上下文
        # context = {'user':user, 'address':address}
        context = {'address':address}

        return render(request, 'user_center_site.html', context)

    def post(self, request):
        """保存用户地址"""

        # 获取用户
        user = request.user

        # 获取地址信息，参数
        recv_name = request.POST.get('recv_name')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        recv_mobile = request.POST.get('recv_mobile')

        # 校验参数
        if not all([recv_name, addr, zip_code, recv_mobile]):
            # 实际中以产品需求而定
            return redirect(reverse('users:address'))

        # 保存地址信息
        address = Address.objects.create(
            user=user,
            receiver_name=recv_name,
            detail_addr=addr,
            zip_code=zip_code,
            receiver_mobile=recv_mobile
        )

        # 响应结果，这里重新刷新页面，顺便测试地址是否保存成功
        return redirect(reverse('users:address'))


class LogoutView(View):
    """退出登录:dnago用户认证系统"""

    def get(self, request):
        # 退出登录本质：清除用户相关的session
        logout(request)

        # 退出登录重定向主页
        return redirect(reverse('goods:index'))


class LoginView(View):
    """登陆"""

    def get(self, request):
        """提供登陆界面"""
        return render(request, 'login.html')

    def post(self, request):
        """处理登陆逻辑"""

        # 1.获取登陆数据，参数
        user_name = request.POST.get('user_name')
        password = request.POST.get('pwd')
        remembered = request.POST.get('remembered')

        # 2.参数校验
        if not all([user_name, password]):
            return redirect(reverse('users:login'))

        # 3.登陆逻辑处理
        # 3.1 验证用户是否存在
        user = authenticate(username=user_name, password=password)
        if user is None:
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})

        # 3.2 判断是否是激活用户
        if user.is_active is False:
            return render(request, 'login.html', {'errmsg':'请去激活'})

        # 3.3 真正的登陆一个用户：就在在服务器和浏览器之间记录登陆状态，session和cookie
        # 提示 : django用户认证系统，提供的login方法，如果需要记录登陆状态，需要搭配django_redis一起使用
        login(request, user)

        # 4.设置cookie中sessionid的有效期
        if remembered != 'on':
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(3600*24*10)

        # 在登录操作完成之后，界面跳转之前，将cookie中的信息合并到redis
        # 查询cookie中的购物车数据
        cart_json = request.COOKIES.get('cart')
        if cart_json is not None:
            cart_dict_cookie = json.loads(cart_json)
        else:
            cart_dict_cookie = {}

        # 查询redis中的购物车数据
        redis_conn = get_redis_connection('default')
        cart_dict_redis = redis_conn.hgetall('cart_%s'%user.id) # cart_dict_redis 里面的key和value是bytes类型

        # 将cookie中的购物车数据合并到redis中
        for sku_id, count in cart_dict_cookie.items():

            # 需要把从cookie中取得的字符串类型的sku_id，转成bytes类型的
            sku_id = sku_id.encode()

            # 提示:需要判断cookie中存在的商品，在redis中是否存在
            if sku_id in cart_dict_redis:
                origin_count = cart_dict_redis[sku_id] # 不是整数类型，是bytes类型
                count += int(origin_count)

            cart_dict_redis[sku_id] = count

        # 一次性向redis中存储多条key和value
        if cart_dict_redis:
            redis_conn.hmset('cart_%s'%user.id, cart_dict_redis)

        # 5.获取next参数
        next = request.GET.get('next')

        if next is None:
            # 5.1. 响应结果：重定向到主页
            response = redirect(reverse('goods:index'))
        else:
            # 5.2. 说明用户是从login_required装饰器引导过来的，哪儿来回哪儿
            if next == '/orders/place':
                response = redirect('/cart')
            else:
                response = redirect(next)

        # 清空cookie
        response.delete_cookie('cart')

        return response


class ActiveView(View):
    """接收激活请求"""

    def get(self, request, token):
        """处理激活逻辑"""

        # 1.创建序列化器:这里的序列化器的参数，要跟生成激活令牌的一致
        serializer = Serializer(settings.SECRET_KEY, 3600)

        # 2.转成成初始状态{"confirm": self.id}
        try:
            result = serializer.loads(token)
        except SignatureExpired:
            return HttpResponse('激活链接过期')

        # 3.取出用户id
        user_id = result.get('confirm')

        # 4.查询要激活的用户
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return HttpResponse('用户不存在')

        # 5.重置is_active=True
        user.is_active = True

        # 6.保存数据到数据库
        user.save()

        # 7.响应结果：跳转到登陆页面，实际开发，根据需求而定
        return HttpResponse('激活成功，这是登陆页面')


class RegisterView(View): # GET --> get
    """类视图：注册"""

    def get(self, request):
        """用于处理get逻辑"""
        return render(request, 'register.html')

    def post(self, request):
        """用于处理post逻辑"""

        # 1.接收用户注册信息、参数
        user_name = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 2.参数校验
        # 2.1 判断参数是否都传入:all(),只有校验的对象都为真，返回True
        if not all([user_name, password, email]):
            # 重新刷新注册页面：具体如何实现，根据公司需求而定
            return redirect(reverse('users:register'))

        # 2.2 校验邮箱地址格式
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg':'邮箱地址格式错误'})

        # 2.3 判断是否勾选用户协议
        if allow != 'on':
            return render(request, 'register.html', {'errmsg':'请勾选用户协议'})

        # 3.保存注册数据:使用django自带的用户认证系统，默认对密码加密在保存，自动保存的
        try:
            # 3.1 判断用户是否存在
            user = User.objects.create_user(user_name, email, password)
        except IntegrityError:
            return render(request, 'register.html', {'errmsg':'用户已存在'})

        # 4.重置激活状态：因为django认证系统默认把用户的激活状态置为True
        user.is_active = False
        user.save()

        # 5.生成激活的token
        token = user.generate_active_token()

        # 6.异步发送激活邮件
        send_active_email.delay(email, user_name, token)

        # 7.响应结果给用户：根据产品需求而定
        return redirect(reverse('goods:index'))


# def register(request):
#     """函数视图：注册"""
#
#     if request.method == 'GET':
#         # 提供注册页面
#         return render(request, 'register.html')
#
#     if request.method == 'POST':
#         # 处理注册的逻辑
#         return HttpResponse('接收到post请求，处理注册逻辑')


