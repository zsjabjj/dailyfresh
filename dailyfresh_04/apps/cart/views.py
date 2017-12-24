from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
import json


# Create your views here.


class DeleteCartView(View):
    """删除购物车数据"""

    def post(self, request):

        # 获取参数：sku_id
        sku_id = request.POST.get('sku_id')

        # 校验参数
        if not sku_id:
            return JsonResponse({'code': 1, 'message': '参数缺少'})

        # 判断用户是否登陆
        if request.user.is_authenticated():
            # 如果是登陆，就从redis是数据库中删除
            redis_conn = get_redis_connection('default')
            user_id = request.user.id
            redis_conn.hdel('cart_%s'%user_id, sku_id)
        else:
            # 如果是未登陆，就从cookie是数据库中删除
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)

                # 判断要删除的key-value是否存在
                if sku_id in cart_dict:
                    del cart_dict[sku_id]

                    # 把删除的结果重新写入到用户的浏览器
                    response = JsonResponse({'code': 0, 'message': '删除成功'})
                    response.set_cookie('cart', json.dumps(cart_dict))

                    return response

        return JsonResponse({'code': 0, 'message': '删除成功'})


class UpdateCartView(View):
    """编辑购物车页面之改变商品数量 + - 修改"""

    def post(self, request):

        # 获取参数：sku_id, count
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验参数all()
        if not all([sku_id, count]):
            return JsonResponse({'code': 1, 'message': '参数不完整'})

        # 判断商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code': 2, 'message': '商品不存在'})

        # 判断count是否是整数
        try:
            count = int(count)
        except Exception:
            return JsonResponse({'code': 3, 'message': '商品数量错误'})

        # 判断库存
        if count > sku.stock:
            return JsonResponse({'code': 4, 'message': '库存不足'})

        # 判断用户是否登陆
        if request.user.is_authenticated():
            # 如果用户登陆，将修改的购物车数据存储到redis中
            redis_conn = get_redis_connection('default')
            user_id = request.user.id
            # 把客户端传入的商品的新的信息存储到redis: count就是最终的商品的数量，不需要累加+1
            redis_conn.hset('cart_%s'%user_id, sku_id, count)
            return JsonResponse({'code': 0, 'message': '更新购物车成功'})
        else:
            # 如果用户未登陆，将修改的购物车数据存储到cookie中
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}

            # 把需要更新的商品数据保存到字典中: count就是最终的商品的数量，不需要累加+1
            cart_dict[sku_id] = count

            # 使用json把cart_dict转成json格式的字符串
            new_cart_josn = json.dumps(cart_dict)

            response = JsonResponse({'code': 0, 'message': '更新购物车成功'})

            # 写入新的购物车信息到cookie
            response.set_cookie('cart', new_cart_josn)

            # 响应结果
            return response


class CartInfoView(View):
    """展示商品购物车列表数据"""

    def get(self, request):

        # 判断用户是否登陆
        if request.user.is_authenticated():
            # 用户登陆,查询redis里面的购物车数据
            redis_conn = get_redis_connection('default')
            user_id = request.user.id
            cart_dict = redis_conn.hgetall('cart_%s'%user_id)
        else:
            # 用户未登录，查询cookie里面的购物车数据
            cart_json = request.COOKIES.get('cart')
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}

        # 定义临时容器
        skus = []
        total_amount = 0
        total_count = 0

        # 遍历字典cart_dict 'cart':{'sku_1':2, 'sku_5':2}
        for sku_id, count in cart_dict.items():

            # 查询商品sku信息
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                continue # 如果有错，就跳过，接着遍历下一个

            # 把coun转成整数，因为redis_conn取得的字典的key和value是bytes类型的。但是cookie里面的是数字
            count = int(count)
            amount = sku.price * count

            # 动态生成属性，绑定数量
            sku.amount = amount
            sku.count = count
            # 使用列表存储sku
            skus.append(sku)

            # 计算总价和总商品数量
            total_amount += amount
            total_count += count

        # 构造上下文
        context = {
            'skus':skus,
            'total_amount':total_amount,
            'total_count':total_count
        }

        # 渲染模板
        return render(request, 'cart.html', context)


class AddCartView(View):
    """添加购物车"""

    def post(self, request):

        # 接收数据：sku_id，count
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验参数all()
        if not all([sku_id, count]):
            return JsonResponse({'code': 1, 'message': '参数不完整'})

        # 判断商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'code': 2, 'message': '商品不存在'})

        # 判断count是否是整数
        try:
            count = int(count)
        except Exception:
            return JsonResponse({'code': 3, 'message': '商品数量错误'})

        # 判断库存
        if count > sku.stock:
            return JsonResponse({'code': 4, 'message': '库存不足'})

        # 判断用户是否登陆
        if request.user.is_authenticated():
            # 用户登陆时，操作redis数据库，保存购物车数据
            # 接收数据：user_id，sku_id，count
            user_id = request.user.id

            # 操作redis数据库存储商品到购物车 hset cart_userid sku_id count 'cart_1':{'sku_1':10,'sku_2':20}
            redis_conn = get_redis_connection('default')
            # 先尝试获取要存储到购物车的商品是否存在
            origin_count = redis_conn.hget('cart_%s'%user_id, sku_id)

            if origin_count is not None:
                count += int(origin_count) # origin_count不是整数

            # 这个写法，保证用户要添加的购物车数据无论是否存在，都会正确的计算
            redis_conn.hset('cart_%s'%user_id, sku_id, count)

            # 为了配合前端展示商品在购物车的总数，后台需要查询购物车的所有的商品的数量求和
            cart_num = 0
            cart_dict = redis_conn.hgetall('cart_%s'%user_id)
            for val in cart_dict.values():
                cart_num += int(val)

            # json方式响应添加购物车结果
            return JsonResponse({'code': 0, 'message': '添加购物车成功', 'cart_num': cart_num})

        else:
            # 尝试获取cookie中的购物车信息
            cart_json = request.COOKIES.get('cart')
            # 判断用户是否操作cookie存储购物车数据
            if cart_json is not None:
                # 得到购物车的字典信息
                cart_dict = json.loads(cart_json)
            else:
                # 用户没有在cookie中保存购物车数据
                cart_dict = {}

            # 判断用户要存储的商品在cookie中是否已经存在
            if sku_id in cart_dict:
                origin_count = cart_dict[sku_id]
                count += int(origin_count)

            # 把更新数量后的商品信息写入到字典中
            cart_dict[sku_id] = count

            # 把cart_dict转成json字符串
            new_cart_json = json.dumps(cart_dict)

            # 计算在购物车中的总数，方便前端展示出效果
            cart_num = 0
            for val in cart_dict.values():
                cart_num += int(val)

            response = JsonResponse({'code':0, 'message':'添加购物车成功', 'cart_num':cart_num})

            # 将购物车数据写入到cookie
            response.set_cookie('cart', new_cart_json)

            return response