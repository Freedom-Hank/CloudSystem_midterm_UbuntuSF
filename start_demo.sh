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

# ------------------------------------------------------------------
# 前置檢查：等 Node 1 真的看到全部 6 台節點都在線才開打。
# 目的是避免「對面 Macbook 上的容器還沒進入監聽 → 錯過 SYSTEM airdrop」
# 造成晚啟動節點整本帳本是空的這個常見 demo bug。
# 最多等 60 秒（30 次 × 2 秒）。
# ------------------------------------------------------------------
# EXPECTED_NODES 可由外部環境變數覆寫：
#   - 完整 demo (PC + Macbook 全 6 台)：EXPECTED_NODES=6（預設）
#   - 單人 demo (只有 PC 上 3 台 Client)：EXPECTED_NODES=3
EXPECTED_NODES="${EXPECTED_NODES:-6}"
echo "[Pre-check] 等待全部 ${EXPECTED_NODES} 個節點上線..."
for i in $(seq 1 15); do
    ONLINE=$(curl -s http://localhost:8081/api/peers \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('online_count', 0))" \
        2>/dev/null || echo 0)
    echo "[Pre-check] 嘗試 ${i}/15 - 目前在線: ${ONLINE}/${EXPECTED_NODES}"
    if [ "$ONLINE" = "$EXPECTED_NODES" ]; then
        echo "[Pre-check] ✅ 全部節點已在線，開始送交易"
        break
    fi
    sleep 2
done

if [ "$ONLINE" != "$EXPECTED_NODES" ]; then
    echo "[Pre-check] ⚠️ 60 秒內未湊齊 ${EXPECTED_NODES} 個節點 (目前 ${ONLINE})"
    echo "[Pre-check]    仍會繼續執行 auto_tx.py，但離線節點將錯過 SYSTEM airdrop"
    echo "[Pre-check]    可能原因：對面機器尚未啟動 / Mac→PC UDP 被防火牆擋住"
fi

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
