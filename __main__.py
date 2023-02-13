import proxy.conf_parser as config
from proxy.proxy2proxies import Proxy


if __name__ == '__main__':
    proxy = Proxy("0.0.0.0", 3000, config.proxies, config.chain_n, config.tor)
    proxy.run()