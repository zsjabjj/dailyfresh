from django.contrib import admin
from goods.models import GoodsCategory, Goods, GoodsSKU, IndexPromotionBanner
from celery_tasks.tasks import generate_static_index_html
from django.core.cache import cache

# Register your models here.


class BaseAdmin(admin.ModelAdmin):
    """商品活动模型类的管理类"""

    def save_model(self, request, obj, form, change):
        """当运维界面中保存数据时会调用的"""

        # 实现父类保存数据到数据库的操作
        obj.save()
        # 触发celery异步生成静态页面
        generate_static_index_html.delay()
        # 凡是后台更新了数据，需要立即删除缓存
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """当运维界面中删除数据时会调用的"""

        # 实现父类删除数据库数据的操作
        obj.delete()
        # 触发celery异步生成静态页面
        generate_static_index_html.delay()
        # 凡是后台更新了数据，需要立即删除缓存
        cache.delete('index_page_data')


class IndexPromotionBannerAdmin(BaseAdmin):
    # list_display = ['name']
    pass

class GoodsCategoryAdmin(BaseAdmin):
    # list_display = ['name']
    pass

admin.site.register(GoodsCategory, GoodsCategoryAdmin)
admin.site.register(Goods)
admin.site.register(GoodsSKU)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)