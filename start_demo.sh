#!/bin/bash
# Demo bootstrap：清掉舊帳本 -> 起 docker -> 灌 100 筆測試交易
set -e

HOST_IP="${HOST_IP:-localhost}"

# 清除上一輪殘留的帳本
rm -f ./storage/client{1,2,3}/*.txt

# 重啟三個 P2P 節點
docker-compose down
docker-compose up -d --build

# 容器要幾秒才會把 Flask 拉起來，auto_tx.py 內部還會自己 retry
sleep 3

python3 auto_tx.py

cat <<EOF

完成，節點瀏覽器網址：
  Client 1  http://${HOST_IP}:8081
  Client 2  http://${HOST_IP}:8082
  Client 3  http://${HOST_IP}:8083
  Client 4  http://100.122.78.117:8083
  Client 5  http://100.122.78.117:8083
  Client 6  http://100.122.78.117:8083
EOF
