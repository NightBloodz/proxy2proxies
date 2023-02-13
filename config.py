import configparser

config = configparser.ConfigParser()
config.read('proxy2proxies.conf')

proxies = config.items('PROXY_LIST')

chain_n = int(config['PROXY_CONF']['ProxiesToChain'])
tor = bool(config['PROXY_CONF']['UseTor'])




for n, proxy in enumerate(proxies):
    #Convert the port to int and all the tuples to arrays
    proxies[n] = [proxy[0], int(proxy[1])]






