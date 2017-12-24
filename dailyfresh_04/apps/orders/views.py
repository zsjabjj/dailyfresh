from django.shortcuts import render,redirect
from django.views.generic import View
from utils.views import LoginRequiredMixin,LoginRequiredJSONMixin,TransactionAtomicMixin
from django.core.urlresolvers import reverse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from users.models import Address
from django.http import JsonResponse
from orders.models import OrderInfo, OrderGoods
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator,EmptyPage
from alipay import AliPay
from django.conf import settings
import os
from django.core.cache import cache


# Create your views here.


class CommentOrderView(LoginRequiredMixin, View):
    """评论"""

    """订单评论"""

    def get(self, request, order_id):
        """提供评论页面"""

        # 查询哪个用户要评论我的上平
        user = request.user

        # 查询要评价的订单
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        # 利用python的动态的，面向对象的特性，动态的给对象添加属性
        order.status_name = OrderInfo.ORDER_STATUS[order.status]
        order.skus = []
        order_skus = order.ordergoods_set.all()
        for order_sku in order_skus:
            sku = order_sku.sku
            sku.count = order_sku.count
            sku.amount = sku.price * sku.count
            order.skus.append(sku)

        return render(request, "order_comment.html", {"order": order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("orders:info"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        for i in range(1, total_count + 1):
            sku_id = request.POST.get("sku_%d" % i)
            content = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

            # 清除商品详情缓存
            cache.delete("detail_%s" % sku_id)

        order.status = OrderInfo.ORDER_STATUS_ENUM["FINISHED"]
        order.save()

        return redirect(reverse("orders:info", kwargs={"page": 1}))


class CheckPayView(LoginRequiredJSONMixin ,View):
    # 查询订单信息

    def get(self, request):
        # 获取订单id
        order_id = request.GET.get('order_id')

        # 校验订单
        if not order_id:
            return JsonResponse({'code': 2, 'message': '订单id错误'})

        # 获取订单信息
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=request.user,
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"],
                                          pay_method=OrderInfo.PAY_METHODS_ENUM["ALIPAY"])
        except OrderInfo.DoesNotExist:
            return JsonResponse({'code': 3, 'message': '订单错误'})

        # 创建用于支付宝支付的对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/orders/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/orders/alipay_public_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False 配合沙箱模式使用
        )

        while True:
            # 查询支付结果:返回字典
            response = alipay.api_alipay_trade_query(order_id)

            # 判断支付结果
            code = response.get('code')  # 支付宝接口调用结果的标志
            trade_status = response.get('trade_status')  # 用户支付状态

            if code == '10000' and trade_status == 'TRADE_SUCCESS':
                # 表示用户支付成功
                # 设置订单的支付状态为待评论
                order.status = OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT']
                # 设置支付宝对应的订单编号
                order.trade_id = response.get('trade_no')
                order.save()

                # 返回json，告诉前端结果
                return JsonResponse({'code': 0, 'message': '支付成功'})

            elif code == '40004' or (code == '10000' and trade_status == 'WAIT_BUYER_PAY'):
                # 表示支付宝的接口暂时调用失败，网络延迟，订单还未生成；or 等待订单的支付
                # 继续查询
                continue
            else:
                # 支付失败，返回支付失败的通知
                return JsonResponse({'code': 4, 'message': '支付失败'})

class PayView(LoginRequiredJSONMixin, View):
    """接收用户的要支付的订单信息"""

    def post(self, request):
        # 接收order_id
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'code': 2, 'message': 'order_id错误'})

        # 查询：需要查询出订单信息，将来交给支付宝
        try:
            # id正确，user正确，待支付，支付方式是支付宝
            order = OrderInfo.objects.get(order_id=order_id, user=request.user,
                                          status=OrderInfo.ORDER_STATUS_ENUM["UNPAID"],
                                          pay_method=OrderInfo.PAY_METHODS_ENUM["ALIPAY"])
        except OrderInfo.DoesNotExist:
            return JsonResponse({'code': 3, 'message': '订单不存在'})

        # 对接到支付宝
        # 创建用于支付宝支付的对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/orders/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/orders/alipay_public_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False 配合沙箱模式使用,沙箱模式写True
        )

        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),  # 将浮点数转成字符串
            subject='天天生鲜',
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 拼接访问支付宝的请求地址
        url = settings.ALIPAY_URL + '?' + order_string

        return JsonResponse({'code': 0, 'message': '支付成功', 'url': url})


class UserOrdersView(LoginRequiredMixin, View):
    """用户订单页面"""

    def get(self, request, page):
        user = request.user
        # 查询订单
        orders = user.orderinfo_set.all().order_by("-create_time")

        for order in orders:
            order.status_name = OrderInfo.ORDER_STATUS[order.status]
            order.pay_method_name = OrderInfo.PAY_METHODS[order.pay_method]
            order.skus = []
            order_skus = order.ordergoods_set.all()
            for order_sku in order_skus:
                sku = order_sku.sku
                sku.count = order_sku.count
                sku.amount = sku.price * sku.count
                order.skus.append(sku)

        # 分页
        page = int(page)
        try:
            paginator = Paginator(orders, 2)
            page_orders = paginator.page(page)
        except EmptyPage:
            # 如果传入的页数不存在，就默认给第1页
            page_orders = paginator.page(1)
            page = 1

        # 页数
        page_list = paginator.page_range

        context = {
            "orders": page_orders,
            "page": page,
            "page_list": page_list,
        }

        return render(request, "user_center_order.html", context)


class CommitOrderView(LoginRequiredJSONMixin , TransactionAtomicMixin, View):
    """提交订单"""

    def post(self, request):
        # 获取参数：user,address_id,pay_method,sku_id,count
        user = request.user
        address_id = request.POST.get('address_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids') # sku_ids = '1,2,3' 因为ajax没有一键多值

        # 校验参数：all([address_id, sku_ids, pay_method])
        if not all([address_id, sku_ids, pay_method]):
            return JsonResponse({'code': 2, 'message': '缺少参数'})

        # 判断地址
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return JsonResponse({'code': 3, 'message': '地址不存在'})

        # 判断支付方式
        if pay_method not in OrderInfo.PAY_METHOD:
            return JsonResponse({'code': 4, 'message': '支付方式错误'})

        # 创建redis连接对象
        redis_conn = get_redis_connection('default')
        cart_dict = redis_conn.hgetall('cart_%s'%user.id)

        # 定义临时的变量
        total_count = 0
        total_amount = 0

        # 创建的是Django维护的订单的id:# '20171222181503'+'userid'
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 在操作数据库以前创建保存点，中途如果有异常，就回到保存点(回滚)
        save_ponit = transaction.savepoint()

        # 尝试暴力回滚
        try:
            # 在创OrderGoods，之前，先把OrderInfo创建好
            order = OrderInfo.objects.create(
                order_id = order_id,
                user = user,
                address = address,
                total_amount = 0,
                trans_cost = 10,
                pay_method = pay_method,
            )

            sku_ids = sku_ids.split(',') # '1,2'
            # 判断商品是否存在
            for sku_id in sku_ids:

                for i in range(3):

                    # 遍历sku_ids，循环取出sku
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # 回滚
                        transaction.savepoint_rollback(save_ponit)
                        return JsonResponse({'code': 5, 'message': '商品不存在'})

                    # 获取商品数量，判断库存 (redis)
                    sku_count = cart_dict.get(sku_id.encode())
                    sku_count = int(sku_count)

                    if sku_count > sku.stock:
                        # 回滚
                        transaction.savepoint_rollback(save_ponit)
                        return JsonResponse({'code': 6, 'message': '库存不足'})

                    # 模拟网络延迟
                    # import time
                    # time.sleep(10)

                    # 获取原有的库存
                    origin_stock = sku.stock
                    new_stock = origin_stock - sku_count
                    news_sales = sku.sales + sku_count
                    # 使用乐观锁，更新数据库的库存和销量
                    result = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock,sales=news_sales)

                    # 尝试购买三次
                    if 0 == result and i < 2:
                        continue # 继续购买
                    elif 0 == result and i == 2:
                        # 回滚
                        transaction.savepoint_rollback(save_ponit)
                        return JsonResponse({'code': 7, 'message': '下单失败'})

                    # 保存订单商品数据OrderGoods(能执行到这里说明无异常)
                    OrderGoods.objects.create(
                        order = order,
                        sku = sku,
                        count = sku_count,
                        price = sku.price,
                    )

                    # 计算总数和总金额
                    total_count += sku_count
                    total_amount += (sku_count * sku.price)

                    break

            # 修改订单信息里面的总数和总金额(OrderInfo)
            order.total_count = total_count
            order.total_amount = total_amount + 10
            order.save()

        except Exception:
            # 回滚
            transaction.savepoint_rollback(save_ponit)
            return JsonResponse({'code': 8, 'message': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_ponit)

        # 订单生成后删除购物车(hdel)
        redis_conn.hdel('cart_%s'%user.id, *sku_ids)

        # 响应结果
        return JsonResponse({'code': 0, 'message': '下单成功'})


class PlaceOrderView(LoginRequiredMixin ,View):
    """订单确认"""

    def post(self, request):

        # 接收参数：user,sku_ids,count
        sku_ids = request.POST.getlist('sku_ids') # [1,2,3]
        count = request.POST.get('count')

        # 校验参数
        if not sku_ids:
            # 到购物车再看看，实际开发中，根据需求而定
            return redirect(reverse('cart:info'))

        # 定义临时容器
        skus = []
        total_count = 0 # 商品总数
        total_sku_amount = 0 # 商品总金额，不包含邮费
        trans_cost = 10 # 邮费

        # 创建redis连接对象
        redis_conn = get_redis_connection('default')
        user_id = request.user.id

        # 判断count是否有值
        if count is None:
            # 表示从购物车过来的
            for sku_id in sku_ids:
                # 查询商品信息
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return redirect(reverse('cart:info'))

                # 商品数量从redis中获取count
                cart_dict = redis_conn.hgetall('cart_%s'%user_id)
                sku_count = cart_dict.get(sku_id.encode())
                sku_count = int(sku_count)

                # 计算小计
                amount = sku_count * sku.price

                # 封装count和amount
                sku.count = sku_count
                sku.amount = amount
                skus.append(sku)

                # 累加数量和金额
                total_count += sku_count
                total_sku_amount += amount
        else:
            # 表示从详情的立即购买过来的
            for sku_id in sku_ids:
                # 查询商品信息
                try:
                    sku = GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return redirect(reverse('goods:detail', args=sku_id))

                # 商品数量从request中获取
                try:
                    sku_count = int(count)
                except Exception:
                    return redirect(reverse('goods:detail', args=sku_id))

                # 计算小计
                amount = sku_count * sku.price

                # 封装count和amount
                sku.count = sku_count
                sku.amount = amount
                skus.append(sku)

                # 累加数量和金额
                total_count += sku_count
                total_sku_amount += amount

                # 把立即购买的商品添加到购物车
                redis_conn.hset('cart_%s'%user_id, sku_id, sku_count)

        # 实付款=商品总金额+邮费
        total_amount = total_sku_amount + trans_cost

        # 查询用户地址信息
        try:
            address = Address.objects.filter(user=request.user).latest('create_time')
        except Address.DoesNotExist:
            address = None

        # 构造上下文
        context = {
            'skus':skus,
            'total_count':total_count,
            'total_sku_amount':total_sku_amount,
            'trans_cost':trans_cost,
            'total_amount':total_amount,
            'address':address,
            'sku_ids':','.join(sku_ids) # '1,2'
        }

        # 渲染模板
        return render(request, 'place_order.html', context)
