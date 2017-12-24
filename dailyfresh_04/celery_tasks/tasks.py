"""
定义异步任务的地方
发送邮件的异步任务
"""

import os
os.environ["DJANGO_SETTINGS_MODULE"] = "dailyfresh_04.settings"
# 放到celery服务器上时将注释打开
#import django
#django.setup()

from django.core.mail import send_mail
from celery import Celery
from django.conf import settings
from goods.models import GoodsCategory,IndexGoodsBanner,IndexPromotionBanner,IndexCategoryGoodsBanner
from django.template import loader


# 创建celery客户端
app = Celery('celery_tasks.tasks', broker='redis://192.168.243.193/4')

@app.task
def send_active_email(to_email, user_name, token):
    """封装发送邮件任务"""

    subject = "天天生鲜用户激活"  # 标题
    body = ""  # 文本邮件体
    sender = settings.EMAIL_FROM  # 发件人
    receiver = [to_email]  # 接收人
    html_body = '<h1>尊敬的用户 %s, 感谢您注册天天生鲜！</h1>' \
                '<br/><p>请点击此链接激活您的帐号<a href="http://127.0.0.1:8000/users/active/%s">' \
                'http://127.0.0.1:8000/users/active/%s</a></p>' % (user_name, token, token)
    send_mail(subject, body, sender, receiver, html_message=html_body)


@app.task
def generate_static_index_html():
    """生成主页对应的静态文件"""

    # 查询用户信息：request.user
    # 查询商品分类信息
    categorys = GoodsCategory.objects.all()

    # 查询图片轮播信息
    index_goods_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 查询商品活动信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 查询商品分类列表信息
    for category in categorys:
        title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0).order_by('index')
        category.title_banners = title_banners

        image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by('index')
        category.image_banners = image_banners

    # 购物车信息：此时暂不处理，等到购物车模块时再去处理
    cart_num = 0

    # 构造上下文
    context = {
        'categorys': categorys,
        'index_goods_banners': index_goods_banners,
        'promotion_banners': promotion_banners,
        'cart_num': cart_num
    }

    # 渲染static_index.html模板，然后把渲染的static_index.html模板写入到文件中
    # 获取模板
    template = loader.get_template('static_index.html')
    # 上下文渲染模板
    html_data = template.render(context)
    # 指定静态html页面在celery服务器路径
    file_path = os.path.join(settings.STATICFILES_DIRS[0], 'index.html')
    # 把渲染的结果写入到文件中
    with open(file_path, 'w') as f:
        f.write(html_data)























