#-*- coding:utf-8 -*-    --------------Ashare 股票行情数据双核心版( https://github.com/mpquant/Ashare ) 
import json,requests,datetime;      import pandas as pd  #

#腾讯日线
def get_price_day_tx(code, end_date='', count=10, frequency='1d'):     #日线获取  
    unit='week' if frequency in '1w' else 'month' if frequency in '1M' else 'day'     #判断日线，周线，月线
    if end_date:  end_date=end_date.strftime('%Y-%m-%d') if isinstance(end_date,datetime.date) else end_date.split(' ')[0]
    end_date='' if end_date==datetime.datetime.now().strftime('%Y-%m-%d') else end_date   #如果日期今天就变成空    
    URL=f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{unit},,{end_date},{count},qfq'     
    st= json.loads(requests.get(URL).content);    ms='qfq'+unit;      stk=st['data'][code]   
    print(st)

    buf=stk[ms] if ms in stk else stk[unit]       #指数返回不是qfqday,是day
    df=pd.DataFrame(buf,columns=['time','open','close','high','low','volume'],dtype='float')     
    df.time=pd.to_datetime(df.time);    df.set_index(['time'], inplace=True);   df.index.name=''          #处理索引 
    return df

#腾讯分钟线
def get_price_min_tx(code, end_date=None, count=10, frequency='1d'):    #分钟线获取 
    ts=int(frequency[:-1]) if frequency[:-1].isdigit() else 1           #解析K线周期数
    if end_date: end_date=end_date.strftime('%Y-%m-%d') if isinstance(end_date,datetime.date) else end_date.split(' ')[0]        
    URL=f'http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},m{ts},,{count}' 
    st= json.loads(requests.get(URL).content);       buf=st['data'][code]['m'+str(ts)] 
    df=pd.DataFrame(buf,columns=['time','open','close','high','low','volume','n1','n2'])   
    df=df[['time','open','close','high','low','volume']]    
    df[['open','close','high','low','volume']]=df[['open','close','high','low','volume']].astype('float')
    df.time=pd.to_datetime(df.time);   df.set_index(['time'], inplace=True);   df.index.name=''          #处理索引     
    df['close'][-1]=float(st['data'][code]['qt'][code][3])                #最新基金数据是3位的
    return df


#sina新浪全周期获取函数，分钟线 5m,15m,30m,60m  日线1d=240m   周线1w=1200m  1月=7200m
def get_price_sina(code, end_date='', count=10, frequency='60m'):    #新浪全周期获取函数    
    frequency=frequency.replace('1d','240m').replace('1w','1200m').replace('1M','7200m');   mcount=count
    ts=int(frequency[:-1]) if frequency[:-1].isdigit() else 1       #解析K线周期数
    if (end_date!='') & (frequency in ['240m','1200m','7200m']): 
        end_date=pd.to_datetime(end_date) if not isinstance(end_date,datetime.date) else end_date    #转换成datetime
        unit=4 if frequency=='1200m' else 29 if frequency=='7200m' else 1    #4,29多几个数据不影响速度
        count=count+(datetime.datetime.now()-end_date).days//unit            #结束时间到今天有多少天自然日(肯定 >交易日)        
        #print(code,end_date,count)    
    URL=f'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={code}&scale={ts}&ma=5&datalen={count}' 
    
    # print(URL)

    dstr= json.loads(requests.get(URL).content);       
    
    # print(dstr)

    #df=pd.DataFrame(dstr,columns=['day','open','high','low','close','volume'],dtype='float') 
    df= pd.DataFrame(dstr,columns=['day','open','high','low','close','volume'])
    df['open'] = df['open'].astype(float); df['high'] = df['high'].astype(float);                          #转换数据类型
    df['low'] = df['low'].astype(float);   df['close'] = df['close'].astype(float);  df['volume'] = df['volume'].astype(float)    
    df.day=pd.to_datetime(df.day);    df.set_index(['day'], inplace=True);     df.index.name=''            #处理索引                 
    if (end_date!='') & (frequency in ['240m','1200m','7200m']): return df[df.index<=end_date][-mcount:]   #日线带结束时间先返回              
    return df

def get_price(code, end_date='',count=10, frequency='1d', fields=[]):        #对外暴露只有唯一函数，这样对用户才是最友好的  
    xcode= code.replace('.XSHG','').replace('.XSHE','')                      #证券代码编码兼容处理 
    xcode='sh'+xcode if ('XSHG' in code)  else  'sz'+xcode  if ('XSHE' in code)  else code     

    if  frequency in ['1d','1w','1M']:   #1d日线  1w周线  1M月线
         try:    return get_price_sina( xcode, end_date=end_date,count=count,frequency=frequency)   #主力
         except: return get_price_day_tx(xcode,end_date=end_date,count=count,frequency=frequency)   #备用                    
    
    if  frequency in ['1m','5m','15m','30m','60m']:  #分钟线 ,1m只有腾讯接口  5分钟5m   60分钟60m
         if frequency in '1m': return get_price_min_tx(xcode,end_date=end_date,count=count,frequency=frequency)
         try:    return get_price_sina(  xcode,end_date=end_date,count=count,frequency=frequency)   #主力   
         except: return get_price_min_tx(xcode,end_date=end_date,count=count,frequency=frequency)   #备用



def get_stock_quote(symbol):
    url = f"http://hq.sinajs.cn/list={symbol}"
    headers = {'referer': 'https://finance.sina.com.cn/'}
    response = requests.get(url, headers=headers)
    # response = requests.get(url)
    data = response.text.split("=")[1].strip('"').split(",")
    name = data[0]
    price = float(data[3])
    return name, price

if __name__ == '__main__':    
    df=get_price('sh600036',frequency='1d',count=1)      #支持'1d'日, '1w'周, '1M'月  
    print('上证指数日线行情\n',df)
    

    symbol = "sh600036"
    name, price = get_stock_quote(symbol)
    print(f"股票代码：{symbol}")
    print(f"股票名称：{name}")
    print(f"股票价格：{price}")



    url = 'http://hq.sinajs.cn/list=sh600036'
    # response = requests.get(url)
    headers = {'referer': 'https://finance.sina.com.cn/'}
    response = requests.get(url, headers=headers)
    data = response.text.split(',')

    print(f"股票名称: {data[0]}")
    print(f"今日开盘价: {data[1]}")
    print(f"昨日收盘价: {data[2]}")
    print(f"现价: {data[3]}")
    print(f"今日最高价: {data[4]}")
    print(f"今日最低价: {data[5]}")
    print(f"竞买价: {data[6]}")
    print(f"竞卖价: {data[7]}")
    print(f"成交的股票数: {data[8]}")
    print(f"成交金额: {data[9]}")
    print(f"买 1 手: {data[10]}")
    print(f"买 1 报价: {data[11]}")
    print(f"买 2 手: {data[12]}")
    print(f"买 2 报价: {data[13]}")
    print(f"买 3 手: {data[14]}")
    print(f"买 3 报价: {data[15]}")
    print(f"买 4 手: {data[16]}")
    print(f"买 4 报价: {data[17]}")
    print(f"买 5 手: {data[18]}")
    print(f"买 5 报价: {data[19]}")
    print(f"卖 1 手: {data[20]}")
    print(f"卖 1 报价: {data[21]}")
    print(f"卖 2 手: {data[22]}")
    print(f"卖 2 报价: {data[23]}")
    print(f"卖 3 手: {data[24]}")
    print(f"卖 3 报价: {data[25]}")
    print(f"卖 4 手: {data[26]}")
    print(f"卖 4 报价: {data[27]}")
    print(f"卖 5 手: {data[28]}")
    print(f"卖 5 报价: {data[29]}")
    print(f"日期: {data[30]}")
    print(f"时间: {data[31]}")

    # df=get_price('000001.XSHG',frequency='15m',count=10)  #支持'1m','5m','15m','30m','60m'
    # print('上证指数分钟线\n',df)

# Ashare 股票行情数据( https://github.com/mpquant/Ashare ) 
