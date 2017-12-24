from django.shortcuts import render, redirect
from django.views.generic import View
from goods.models import GoodsCategory,IndexGoodsBanner,IndexPromotionBanner,IndexCategoryGoodsBanner
from django.core.cache import cache
from django_redis import get_redis_connection
from goods.models import GoodsSKU
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator,EmptyPage
import json


# Create your views here.


class BaseCartView(View):
    """购物车商品总数求和"""

    def get_cart_num(self, request):

        cart_num = 0

        # 查询购物车数据：redis, hset cart_userid sku_id count "cart_userid":{"sku_id":count,...}
        # 判断是否登陆
        if request.user.is_authenticated():

            # 创建redis链接对象
            redis_conn = get_redis_connection('default')
            # 获取use_id
            user_id = request.user.id
            # 查询redis数据库，得到购物车数据（字典）
            cart_dict = redis_conn.hgetall('cart_%s' % user_id)
            # 遍历cart_dict，取出所有的value
            for val in cart_dict.values():
                cart_num += int(val)
        else:
            # 获取cookie终端饿购物车数据
            cart_json = request.COOKIES.get('cart')
            # 判断用户的购物车中，是否有数据
            if cart_json is not None:
                cart_dict = json.loads(cart_json)
            else:
                cart_dict = {}

            # 遍历cart_dict，取出所有的value
            for val in cart_dict.values():
                cart_num += int(val)

        return cart_num


#/list/1/2?sort=default
class ListView(BaseCartView):

    """商品分类列表"""

    def get(self, request, category_id, page_num):
        # 请求参数：category_id,page_num,sort

        # 获取排序规则
        sort = request.GET.get('sort', 'default')

        # 参数校验
        try:
            # 校验category_id
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 查询购物车数据
        cart_num = self.get_cart_num(request)

        # 查询所有商品分类
        categorys = GoodsCategory.objects.all()

        # 查询新品推荐
        new_skus = GoodsSKU.objects.filter(category=category).order_by('-create_time')[:2]

        # 分类商品列表信息：需要排序规则作为查询条件
        if sort == 'price':
            # 按照价格从低到高排序
            skus = GoodsSKU.objects.filter(category=category).order_by('price')
        elif sort == 'hot':
            # 按照销量从高到低排序
            skus = GoodsSKU.objects.filter(category=category).order_by('-sales')
        else: # 'haha'
            skus = GoodsSKU.objects.filter(category=category)
            sort = 'default'


        # 先把page_num转成整数,提示：这里没有异常，因为能够进入到这里，说明正则匹配时通过的
        page_num = int(page_num)
        # 分页器对象
        paginator = Paginator(skus, 2)
        # 页对象
        try:
            # page_num放在后面使用分页器时判断
            page_skus = paginator.page(page_num)
        except EmptyPage:
            page_skus = paginator.page(1)

        # 分页器里面的页面列表
        page_list = paginator.page_range

        # 构造上下文
        context = {
            'sort':sort,
            'category':category,
            'cart_num':cart_num,
            'categorys':categorys,
            'new_skus':new_skus,
            'skus':skus,
            'page_skus':page_skus,
            'page_list': page_list
        }

        # 渲染模板
        return render(request, 'list.html', context)


class DetailView(BaseCartView):
    """商品详细信息页面"""

    def get(self, request, sku_id):

        # 尝试获取缓存数据
        context = cache.get("detail_%s" % sku_id)

        # 如果缓存不存在
        if context is None:
            try:
                # 获取商品信息
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # from django.http import Http404
                # raise Http404("商品不存在!")
                return redirect(reverse("goods:index"))

            # 获取类别
            categorys = GoodsCategory.objects.all()

            # 从订单中获取评论信息
            sku_orders = sku.ordergoods_set.all().order_by('-create_time')[:30]
            if sku_orders:
                for sku_order in sku_orders:
                    sku_order.ctime = sku_order.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    sku_order.username = sku_order.order.user.username
            else:
                sku_orders = []

            # 获取最新推荐
            new_skus = GoodsSKU.objects.filter(category=sku.category).order_by("-create_time")[:2]

            # 获取其他规格的商品:查询的是除了自己以外的，其他所有商品的规格
            # other_skus = GoodsSKU.objects.exclude(id=sku_id)
            # 获取其他规格的商品:查询的是除了自己以外的，同类型的商品的规格
            # 如果要展示草莓的详情，需要显示的是草莓的其他规则
            other_skus = sku.goods.goodssku_set.exclude(id=sku_id)

            context = {
                "categorys": categorys,
                "sku": sku,
                "orders": sku_orders,
                "new_skus": new_skus,
                "other_skus": other_skus
            }

            # 设置缓存
            cache.set("detail_%s"%sku_id, context, 3600)

        # 购物车数量
        cart_num = self.get_cart_num(request)

        # 如果是登录的用户
        if request.user.is_authenticated():
            # 获取用户id
            user_id = request.user.id
            # 从redis中获取购物车信息
            redis_conn = get_redis_connection("default")

            # 浏览记录: lpush history_userid sku_1, sku_2
            # 移除已经存在的本商品浏览记录
            redis_conn.lrem("history_%s"%user_id, 0, sku_id)
            # 添加新的浏览记录
            redis_conn.lpush("history_%s"%user_id, sku_id)
            # 只保存最多5条记录
            redis_conn.ltrim("history_%s"%user_id, 0, 4)

        context.update({"cart_num": cart_num})

        return render(request, 'detail.html', context)


class IndexView(BaseCartView):
    """主页"""

    def get(self, request):
        """提供主页页面"""

        # 在查询数据库之前，读取缓存数据，如果没有缓存数据，就执行查询，反之，直接读取缓存的数据
        context = cache.get('index_page_data')
        if context is None:

            print('没有缓存。需要查询数据库')

            # 查询用户信息：request.user
            # 查询商品分类信息
            categorys = GoodsCategory.objects.all()

            # 查询图片轮播信息
            index_goods_banners = IndexGoodsBanner.objects.all().order_by('index')

            # 查询商品活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

            # 查询商品分类列表信息
            for category in categorys:
                title_banners = IndexCategoryGoodsBanner.objects.filter(category=category,display_type=0).order_by('index')
                category.title_banners = title_banners

                image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by('index')
                category.image_banners = image_banners

            # 构造上下文
            context = {
                'categorys':categorys,
                'index_goods_banners':index_goods_banners,
                'promotion_banners':promotion_banners,
            }

            # 使用cache缓存上下文字典数据到redis是数据库中
            #             key            value  过期时间
            cache.set('index_page_data',context, 3600)

        # 购物车信息
        cart_num = self.get_cart_num(request)
        # 更新购物车数据
        context.update(cart_num=cart_num)

        # 渲染模板
        return render(request, 'index.html', context)
