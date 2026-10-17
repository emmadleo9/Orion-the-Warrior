import time
from orion_app.telegram.proxy_manager import telegram_proxy_manager as pm

for p in pm.get_proxies():
    t = time.time()
    r = pm.test_proxy(p)
    name = str(p.get("name", "?"))[:30]
    print(f"{name:32} online={r['online']} {round(time.time() - t, 2)}s")

t = time.time()
pm.test_all_proxies()
print("test_all_proxies:", round(time.time() - t, 2), "s")
