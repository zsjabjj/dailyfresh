"""
python3语法
view = super().as_view(**initkwargs)

python2语法
view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
"""


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from functools import wraps
from django.db import transaction

class LoginRequiredMixin(object):
    """使用login_required装饰器，装饰as_view()的结果"""

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)


def login_required_json(view_func):
    """提供跟ajax交互的用户验证"""
    # 还原被装饰的视图的名字和说明文档
    @wraps(view_func)
    def wraaper(request, *args, **kwargs):

        # 判断用户是否登陆
        if not request.user.is_authenticated():
            # 如果用户未登录
            return JsonResponse({'code': 1, 'message': '用户未登录'})
        else:
            # 如果用户登录，进入视图函数
            return view_func(request, *args, **kwargs)

    return wraaper


class LoginRequiredJSONMixin(object):
    """使用login_required装饰器，装饰as_view()的结果"""

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredJSONMixin, cls).as_view(**initkwargs)
        return login_required_json(view)


class TransactionAtomicMixin(object):
    """提供事务回滚"""

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(TransactionAtomicMixin, cls).as_view(**initkwargs)
        return transaction.atomic(view)