# 启动程序
nohup ./start_stockdata.sh > nohup.out 2>&1 &

# mysql 中文
SET NAMES utf8mb4;


# 导出当前环境已安装的包到文件
pip3 list --format=freeze > requirements.txt
# 批量安装
pip3 install -r requirements.txt

# 安装ark
pip install --upgrade 'volcengine-python-sdk[ark]'

pip3 install pyyaml
pip3 install dbutils
pip3 install pymysql
pip3 install flask
pip3 install numpy
pip3 install akshare

#yum install openssl-devel

#pip3 install TA-Lib
#pip3 install TA-Lib --trusted-host mirrors.aliyun.com -i http://mirrors.aliyun.com/pypi/simple/

--Anaconda 虚拟环境
https://cloud.tencent.com/developer/article/2063049

--
#安装ta-lib
sudo apt-get update
sudo apt-get install build-essential autoconf automake libtool

#下载库并且编译
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib
#./configure
./configure --prefix=/usr
make
sudo make install

#更新库路径
sudo ldconfig
#安装TA-Lib的Python包
pip install ta-lib





-----
#安装open ssl
https://xdouble.cn/archives/4/

##下载源码包
wget https://github.com/openssl/openssl/releases/download/openssl-3.0.14/openssl-3.0.14.tar.gz

#解压
tar -zxvf openssl-3.0.14.tar.gz

#进入文件夹
cd openssl-3.0.14/
#配置指定安装目录
./config --prefix=/usr/local/openssl
#编译安装
make && make install

##备份
mv /usr/bin/openssl /usr/bin/openssl.old
mv /usr/include/openssl copenssl.old

#新建连接
ln -s /usr/local/openssl/bin/openssl /usr/bin/openssl
ln -s /usr/local/openssl/include/openssl /usr/include/openssl
#库类文件
echo "/usr/local/openssl/lib" >> /etc/ld.so.conf
#重载配置
ldconfig 
-----
#安装python 特别注意ssl要安装
./configure --prefix=/usr/local/python3 --enable-optimizations --with-openssl

make -j4
make install

#加软链
sudo ln -s /usr/local/python3/bin/python3.12 /bin/python3
sudo ln -s /usr/local/python3/bin/pip3.12 /bin/pip3


---
#mysql
docker run --name mysql5.7 -e MYSQL_ROOT_PASSWORD=gamer@home -p 3307:3306 -d mysql:5.7

