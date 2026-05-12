#================================
# M1421070 戴弘奕；M1429012 吳承翰  
#================================
import os
from flask import Flask
import logging
from blockchain import P2PNode
from routes import init_routes

# 隱藏 Flask 開機與運作時的煩人日誌
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

STORAGE_PATH = "/storage"

app = Flask(__name__)

# 全網通訊錄：填入節點的大名單
ALL_NODES = {
    "NODE_4":("100.122.78.117", 8001),
    "NODE_5":("100.122.78.117", 8002),
    "NODE_6":("100.122.78.117", 8003),
    "NODE_1":("100.94.194.29", 8001),
    "NODE_2":("100.94.194.29", 8002),
    "NODE_3":("100.94.194.29", 8003)
    # VM Tailscale IP: 100.119.224.86
}

# 同 host 的 container 之間，UDP/TCP 走 docker 內部主機名而不是 host 的 Tailscale IP。
# 原因：Docker Desktop on Windows/Mac 的「container → host 自己外部 IP → 另一個 container」
# 這條 hairpin NAT 路徑對 UDP 非常不可靠，常常整段封包都到不了，導致同 host 的節點互看離線。
# 改用 docker bridge 上的服務名稱（client1/2/3）就直接走內部網路，跨平台都穩。
LOCAL_HOSTNAMES = {
    8001: "client1",
    8002: "client2",
    8003: "client3",
}

if __name__ == '__main__':
    my_name = os.environ["NODE_NAME"]          # 容器必須帶這個
    my_ip, my_port = ALL_NODES[my_name]
    my_addr = (my_ip, my_port)

    # peers_book: 給共識邏輯用的「node_id -> 實際 sendto 位址」表
    # peers:      給 heartbeat / TX broadcast 直接 sendto 的 (ip, port) list
    peers_book = {}
    peers = []
    for name, (p_ip, p_port) in ALL_NODES.items():
        if name == my_name:
            continue
        if p_ip == my_ip and p_port in LOCAL_HOSTNAMES:
            # 同 host：改走 docker 服務名（bypass hairpin NAT）
            addr = (LOCAL_HOSTNAMES[p_port], p_port)
        else:
            # 跨機：走原本的 Tailscale IP
            addr = (p_ip, p_port)
        peers_book[name] = addr
        peers.append(addr)

    node_instance = P2PNode(
        my_ip, my_port, peers,
        peers_book=peers_book,
        my_node_id=my_name,
    )
    node_instance.start()
    app.register_blueprint(init_routes(node_instance))
    print(f"[Web] {my_name} GUI on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)