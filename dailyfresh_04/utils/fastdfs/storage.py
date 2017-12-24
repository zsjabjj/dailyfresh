from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings

# FastDFSStorage('./client.conf','http://192.168.243.193:8888/')

class FastDFSStorage(Storage):
    """自定义的文件存储系统"""

    def __init__(self, client_conf=None, server_ip=None):

        if client_conf is None:
            client_conf = settings.CLIENT_CONF
        self.client_conf = client_conf

        if server_ip is None:
            server_ip = settings.SERVER_IP
        self.server_ip = server_ip

    def _open(self, name, mode='rb'):
        """打开文件时调用的:主打存储的逻辑，不会涉及到打开"""
        pass

    def _save(self, name, content):
        """保存文件时调用的"""
        # name是要保存到fdfs的文件的名字。content是要保存到fdfs的文件类容对象，File对象。可以直接调用read()方法。读取文件内容

        # 创建fdfs客户端
        client = Fdfs_client(self.client_conf)
        # 读取文件类容二进制数据
        file_data = content.read()
        # 上传到fdfs
        try:
            ret = client.upload_by_buffer(file_data)
        except Exception as e:
            print(e) # 方便自己查看
            raise

        # 判断上传是否成功
        if ret.get('Status') == 'Upload successed.':
            # 上传成功，需要把file_id存储到数据库中
            file_id = ret.get('Remote file_id')
            # 直接return即可，因为将来需要通过站点发布内容，如果是从df_GoodsSKU进入的站点，默认保存到df_GoodsSKU
            return file_id
        else:
            # 上传失败:在封装工具类时，如果有可能出现的地方，交给框架的使用者解决，写框架的人只需要提示riase
            raise Exception('上传失败')

    def exists(self, name):
        """判断图片在django中是否存在:每次都返回fasle,django不存，都交给fds"""
        return False

    def url(self, name):
        """提供要访问的文件、图片的全路径"""
        # http://192.168.243.193:8888/group1/M00/00/00/wKjzwVoZKa-AN83fAALb6Vx4KgI69.jpeg
        return self.server_ip + name


