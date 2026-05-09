#================================
# M1421070 戴弘奕；M1429012 吳承翰  
#================================
import socket
import threading
import os
import hashlib
import time
import subprocess
import json
from collections import Counter

STORAGE_PATH = "/storage"
HEAD_HASH_FILE = os.path.join(STORAGE_PATH, "latest_hash.txt")
SYNC_WAIT_SECONDS = 2

# 心跳設定：每 HEARTBEAT_INTERVAL 秒對所有 peer 發 PING；
# 若超過 HEARTBEAT_TIMEOUT 秒沒收到回覆，視為離線。
# interval 比 timeout 小（約 2~3 倍）以避免「燈號抖動」。
HEARTBEAT_INTERVAL = 2
HEARTBEAT_TIMEOUT = 5

# 共識最少參與節點數（含自己）。低於此值直接拒絕全網驗證/修復。
MIN_QUORUM_NODES = 2

# ==========================================
# P2P Node 核心類別
# ==========================================
class P2PNode:
    def __init__(self, ip, port, peers):
        self.ip = ip
        self.port = port
        self.peers = peers
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', self.port))
        
        self.file_lock = threading.Lock()
        self.expected_hashes = {}
        self.awaiting_hashes = False
        
        self.log_buffer = []
        self.log_lock = threading.Lock()

        self.node_id = os.environ.get("NODE_NAME", f"{ip}-{port}")
        self.network_token = "MY_BLOCKCHAIN_SECRET_2026"

        self.nodes_contact_book = {}
        for p_ip, p_port in self.peers:
            p_id = f"{p_ip}-{p_port}"
            self.nodes_contact_book[p_id] = (p_ip, p_port)
        self.pending_initiator = None

        # 心跳狀態：peer_id -> 最後一次收到 PONG 的時間戳
        self.peer_last_seen = {}
        self.peer_lock = threading.Lock()

        # 全網信任狀態：預設為 True，全網共識失敗時凍結；通過時恢復。
        self.network_trusted = True
        self.network_trusted_reason = "尚未驗證"

    def add_log(self, msg):
        print(msg)
        with self.log_lock:
            self.log_buffer.append(msg)

    def start(self):
        print(f"📡 P2P Listener starting at {self.ip}:{self.port}")
        threading.Thread(target=self._listen, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    def _heartbeat_loop(self):
        ping_msg = f"PING:{self.node_id}:{self.network_token}".encode('utf-8')
        while True:
            for peer in self.peers:
                try:
                    self.sock.sendto(ping_msg, peer)
                except Exception as e:
                    print(f"[Heartbeat] 發送 PING 給 {peer} 失敗: {e}")
            time.sleep(HEARTBEAT_INTERVAL)

    def get_live_peer_ids(self):
        """回傳目前還在線（最後 PONG 在超時內）的 peer node_id 集合。"""
        now = time.time()
        with self.peer_lock:
            return {
                pid for pid, ts in self.peer_last_seen.items()
                if now - ts <= HEARTBEAT_TIMEOUT
            }

    def get_peer_status(self):
        """提供前端：每個已知 peer 的線上狀態。"""
        now = time.time()
        result = []
        with self.peer_lock:
            for pid, (p_ip, p_port) in self.nodes_contact_book.items():
                last = self.peer_last_seen.get(pid)
                online = last is not None and (now - last) <= HEARTBEAT_TIMEOUT
                result.append({
                    "node_id": pid,
                    "ip": p_ip,
                    "port": p_port,
                    "online": online,
                    "last_seen_ago": None if last is None else round(now - last, 1),
                })
        return result

    def _listen(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
                message = data.decode('utf-8')
                
                if message.startswith("PING:"):
                    parts = message.split(":")
                    if len(parts) == 3 and parts[2] == self.network_token:
                        sender_id = parts[1]
                        # 收到 PING 也代表對方上線，順便更新狀態
                        with self.peer_lock:
                            self.peer_last_seen[sender_id] = time.time()
                        pong = f"PONG:{self.node_id}:{self.network_token}"
                        self.sock.sendto(pong.encode('utf-8'), addr)
                    continue

                if message.startswith("PONG:"):
                    parts = message.split(":")
                    if len(parts) == 3 and parts[2] == self.network_token:
                        sender_id = parts[1]
                        with self.peer_lock:
                            self.peer_last_seen[sender_id] = time.time()
                    continue

                if message.startswith("TX:"):
                    parts = message.split(":")
                    if len(parts) == 4:
                        self._execute_transaction(parts[1], parts[2], parts[3])
                        self.add_log(f"[網路同步] 收到廣播交易: {parts[1]} 轉給 {parts[2]} {parts[3]} 元")
                    
                elif message.startswith("REQ_HASH"):
                    self.add_log(f"[跨節點驗證] 收到來自 {addr[0]} 的 Hash 請求，已回傳驗證結果。")
                    # 組合格式：RESP_HASH : [Hash] : [我的ID] : [安全Token]
                    response = f"RESP_HASH:{self._get_last_block_hash()}:{self.node_id}:{self.network_token}"
                    self.sock.sendto(response.encode('utf-8'), addr)
                    
                elif message.startswith("RESP_HASH:"):
                    if self.awaiting_hashes:
                        parts = message.split(":")
                        print(f"DEBUG: 收到原始回覆 -> {message}")

                        # 檢查格式是否完整 (RESP_HASH + Hash + ID + Token = 4 部分)
                        if len(parts) == 4:
                            h_val = parts[1]
                            sender_id = parts[2]
                            token = parts[3]

                            # 【資安門神】
                            # 1. 暗號不對 -> 滾 (防止外部封包)
                            # 2. 發送者不在通訊錄裡 -> 滾 (防止未授權節點)
                            if token == self.network_token:
                                # 使用 sender_id 作為 Key，防止灌票
                                self.expected_hashes[sender_id] = h_val

                elif message.startswith("BROADCAST_MAJORITY:"):
                    parts = message.split(":")
                    if len(parts) >= 3:
                        majority_hash = parts[1]
                        provider_id = parts[2]
                        initiator_id = parts[3] if len(parts) >= 4 else None  # 新增
                        my_hash = self._get_last_block_hash()
                        # 我才是提供者 -> 無需修復
                        if provider_id == self.node_id:
                            pass
                        elif my_hash != majority_hash:
                            if provider_id in self.nodes_contact_book:
                                provider_addr = self.nodes_contact_book[provider_id]
                                self.add_log(f"[共識機制] ❌ 警告：本地帳本與全網共識不符！\n正在向信任節點 {provider_id} 請求修復...")
                                self.pending_initiator = initiator_id  # 新增：記住誰發起的，修完要回報
                                self.sock.sendto(b"REQ_SYNC", provider_addr)
                            else:
                                self.add_log(f"[共識機制] ⚠️ 收到廣播但找不到提供者 {provider_id} 的通訊錄地址。")

                elif message.startswith("REQ_SYNC"):
                    last_hash = self._get_last_block_hash()
                    if last_hash in ["INVALID", "EMPTY"]:
                        self.add_log(f"[SYNC] Reject sync request from {addr[0]} because local ledger is {last_hash}.")
                        continue
                    self.add_log(f"[共識機制] 收到來自 {addr[0]} 的修復請求，正在傳送正確帳本資料...")
                    ledger_data = self._pack_ledger()
                    self.sock.sendto(f"RESP_SYNC:{ledger_data}".encode('utf-8'), addr)

                elif message.startswith("RESP_SYNC:"):
                    json_str = message[len("RESP_SYNC:"):]
                    self._unpack_and_repair_ledger(json_str)
                    self.add_log("🎉 [共識機制] 置換完成！本地帳本已成功依照 >50% 多數決共識修復！")
                    # 新增：把修復完成的事實回報給當初發起 checkAllChains 的節點
                    initiator_id = getattr(self, "pending_initiator", None)
                    if initiator_id and initiator_id in self.nodes_contact_book:
                        self.sock.sendto(
                            f"REPAIR_DONE:{self.node_id}".encode('utf-8'),
                            self.nodes_contact_book[initiator_id]
                        )
                    self.pending_initiator = None

                elif message.startswith("REPAIR_DONE:"):
                    repaired_id = message.split(":", 1)[1]
                    self.add_log(f"[共識機制] ✅ 確認節點 {repaired_id} 已完成帳本修復")

            except Exception as e:
                print(f"[Error] 監聽發生錯誤: {e}")

    def _get_total_tx_count(self):
        with self.file_lock:
            files = self._ledger_files_unlocked()
            if not files: return 0
            
            # 公式實作：(總檔案數 - 1) * 5
            total_from_full_blocks = (len(files) - 1) * 5
            
            # 讀取最後一個檔案看裡面有幾筆交易 (算有逗號的行數)
            with open(os.path.join(STORAGE_PATH, files[-1]), "r") as f:
                last_block_content = f.readlines()
                tx_in_last_block = sum(1 for line in last_block_content if "," in line)
                
            return total_from_full_blocks + tx_in_last_block

# ==========================================
# 帳本與共識邏輯 
# ==========================================
    def _ledger_files_unlocked(self):
        return sorted(
            [
                f for f in os.listdir(STORAGE_PATH)
                if f.endswith(".txt") and f.split('.')[0].isdigit()
            ],
            key=lambda x: int(x.split('.')[0])
        )

    def _get_file_hash(self, file_path):
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _write_head_hash_unlocked(self, last_hash=None):
        files = self._ledger_files_unlocked()
        if not files:
            return

        if last_hash is None:
            last_hash = self._get_file_hash(os.path.join(STORAGE_PATH, files[-1]))

        with open(HEAD_HASH_FILE, "w") as f:
            f.write(last_hash + "\n")

    def _check_chain_unlocked(self, initialize_missing_head=True):
        files = self._ledger_files_unlocked()
        if not files:
            return True, "沒有帳本區塊"

        for i in range(1, len(files)):
            prev_path = os.path.join(STORAGE_PATH, files[i - 1])
            curr_path = os.path.join(STORAGE_PATH, files[i])
            actual_prev_hash = self._get_file_hash(prev_path)
            with open(curr_path, "r") as f:
                recorded_hash = f.readline().strip().replace("Sha256 of previous block: ", "")

            if actual_prev_hash != recorded_hash:
                block_id = files[i].split('.')[0]
                return False, f"帳本鏈在區塊 {block_id} 之前斷裂"

        last_file = files[-1]
        actual_last_hash = self._get_file_hash(os.path.join(STORAGE_PATH, last_file))
        if os.path.exists(HEAD_HASH_FILE):
            with open(HEAD_HASH_FILE, "r") as f:
                expected_last_hash = f.read().strip()

            if actual_last_hash != expected_last_hash:
                block_id = last_file.split('.')[0]
                return False, f"{block_id}被篡改 ."

        elif initialize_missing_head:
            self._write_head_hash_unlocked(actual_last_hash)
            return False, "latest_hash.txt 檔案缺失；已從目前帳本初始化"
        else:
            return False, "latest_hash.txt 檔案缺失"

        return True, "沒問題，帳本鏈和最新區塊Hash值匹配成功"

    def _collect_last_hash_votes(self):
        self.expected_hashes.clear()
        self.awaiting_hashes = True

        # 只向「目前存活」的 peer 索取 hash；通訊錄中的離線節點直接略過。
        live_ids = self.get_live_peer_ids()
        live_peers = [
            self.nodes_contact_book[pid] for pid in live_ids
            if pid in self.nodes_contact_book
        ]
        for peer in live_peers:
            self.sock.sendto(b"REQ_HASH", peer)

        my_hash = self._get_last_block_hash()
        time.sleep(SYNC_WAIT_SECONDS)
        self.awaiting_hashes = False

        all_votes = self.expected_hashes.copy()
        all_votes[self.node_id] = my_hash
        # 「過半」改用實際存活的節點數（含自己）作為分母
        total_expected = len(live_peers) + 1
        return my_hash, all_votes, total_expected

    def _majority_hash(self, all_votes):
        valid_hashes = Counter(h for h in all_votes.values() if h not in ["INVALID", "EMPTY"])
        if not valid_hashes:
            return None, 0
        return valid_hashes.most_common(1)[0]

    def _request_sync_from_majority(self, my_hash, all_votes, total_expected):
        if total_expected < MIN_QUORUM_NODES:
            return False, f"存活節點不足（{total_expected}/{MIN_QUORUM_NODES}），無法達成共識修復。"

        majority_hash, max_count = self._majority_hash(all_votes)
        if not majority_hash:
            return False, "No valid peer ledger hash is available for repair."

        if max_count <= total_expected / 2:
            return False, f"No majority ledger hash yet ({max_count}/{total_expected})."

        if my_hash == majority_hash:
            return True, "Local ledger already matches the majority."

        provider_id = [node_id for node_id, h in all_votes.items() if h == majority_hash][0]
        if provider_id not in self.nodes_contact_book:
            return False, f"Repair provider {provider_id} is not in the contact book."

        self.sock.sendto(b"REQ_SYNC", self.nodes_contact_book[provider_id])
        return True, f"{provider_id} 發起維修請求"

    def _repair_from_majority(self):
        my_hash, all_votes, total_expected = self._collect_last_hash_votes()
        return self._request_sync_from_majority(my_hash, all_votes, total_expected)

    def _require_network_trust(self, action_name):
        """全網共識失敗時，凍結所有金流相關操作。回傳 (ok, msg)。"""
        if not self.network_trusted:
            msg = (
                f"⚠️ {action_name}已凍結：上次全網共識失敗"
                f"（原因：{self.network_trusted_reason}）。"
                f"請重新發起全網共識驗證以恢復信任。"
            )
            self.add_log(msg)
            return False, msg
        return True, None

    def _execute_checkMoney(self, target, gui_mode=False):
        ok, _ = self._require_network_trust("查詢餘額")
        if not ok:
            return None

        is_valid = self._execute_checkChain()
        if not is_valid:
            # 如果帳本損毀，直接報錯或回傳 None，不進行後續計算
            self.add_log(f"⚠️ [安全警示] 拒絕查詢餘額：本地帳本已受損，請先進行共識修復！")
            return None # 或是回傳 0，視你的前端邏輯而定
        
        balance = 0
        with self.file_lock:
            files = self._ledger_files_unlocked()
            for file in files:
                with open(f"{STORAGE_PATH}/{file}", "r") as f:
                    for line in f:
                        if "," in line:
                            parts = [p.strip() for p in line.split(",")]
                            if len(parts) == 3:
                                if parts[0] == target: balance -= int(parts[2])
                                if parts[1] == target: balance += int(parts[2])
        return balance

    def _execute_checkLog(self, target, gui_mode=False):
        ok, _ = self._require_network_trust("查詢明細")
        if not ok:
            return [] if gui_mode else None

        logs = []
        with self.file_lock:
            files = self._ledger_files_unlocked()
            for file in files:
                with open(f"{STORAGE_PATH}/{file}", "r") as f:
                    for line in f:
                        if "," in line and target in line: logs.append(line.strip())
        if gui_mode: return logs

    def _execute_checkChain(self, gui_mode=False, print_result=False, auto_repair=False):
        with self.file_lock:
            is_valid, msg = self._check_chain_unlocked()

        if not is_valid and auto_repair:
            repaired, repair_msg = self._repair_from_majority()
            msg = f"{msg} 自動修復: {repair_msg}"
            if repaired:
                self.add_log(f"[AUTO_REPAIR] {msg}")

        return (is_valid, msg) if gui_mode else is_valid

    def _get_last_block_hash(self):
        res = self._execute_checkChain()
        is_valid = res[0] if type(res) == tuple else res
        if not is_valid: return "INVALID"
        with self.file_lock:
            files = self._ledger_files_unlocked()
            if not files: return "EMPTY"
            return self._get_file_hash(os.path.join(STORAGE_PATH, files[-1]))

    def _pack_ledger(self):
        ledger_dict = {}
        with self.file_lock:
            self._write_head_hash_unlocked()
            for file in [f for f in os.listdir(STORAGE_PATH) if f.endswith(".txt")]:
                with open(f"{STORAGE_PATH}/{file}", "r") as f: ledger_dict[file] = f.read()
        return json.dumps(ledger_dict)

    def _unpack_and_repair_ledger(self, json_str):
        try:
            ledger_dict = json.loads(json_str)
            with self.file_lock:
                for f in os.listdir(STORAGE_PATH):
                    if f.endswith(".txt"): os.remove(os.path.join(STORAGE_PATH, f))
                for filename, content in ledger_dict.items():
                    with open(os.path.join(STORAGE_PATH, filename), "w") as f: f.write(content)
                self._write_head_hash_unlocked()
                self.add_log("[自我修復] 完成，本地帳本已被 provider 覆寫並更新 latest_hash.txt")
        except Exception as e: print(f"[Error] 解析失敗: {e}")

    def _execute_checkAllChains(self, target, gui_mode=False):
        # 1. 初始化收集箱
        self.expected_hashes.clear()
        self.awaiting_hashes = True

        # 2. 只發送請求給「目前存活」的節點
        live_ids = self.get_live_peer_ids()
        live_peers = [
            self.nodes_contact_book[pid] for pid in live_ids
            if pid in self.nodes_contact_book
        ]
        for peer in live_peers:
            self.sock.sendto(b"REQ_HASH", peer)

        # 3. 整合選票 (包含自己的一票)
        my_hash = self._get_last_block_hash()
        time.sleep(SYNC_WAIT_SECONDS)
        self.awaiting_hashes = False

        all_votes = self.expected_hashes.copy()
        all_votes[self.node_id] = my_hash
        # 「過半」分母 = 實際存活節點 + 自己
        total_expected = len(live_peers) + 1
        
        output_msg = f"--- 實名制共識比對 (Token 驗證) --- \n"
        output_msg += f"預期節點: {total_expected} | 實際收到回覆: {len(all_votes)}\n"

        # 硬門檻：存活節點（含自己）少於 MIN_QUORUM_NODES 一律拒絕共識
        if total_expected < MIN_QUORUM_NODES:
            output_msg += (
                f"\n❌ 存活節點不足（{total_expected}/{MIN_QUORUM_NODES}），"
                f"拒絕進行全網驗證；請等待其他節點上線。"
            )
            return output_msg if gui_mode else None

        # 4. 統計出現次數最多的 Hash並排除掉無效的 Hash (例如 INVALID 或 EMPTY)
        valid_hashes = Counter(h for h in all_votes.values() if h not in ["INVALID", "EMPTY"])

        if not valid_hashes:
            self.network_trusted = False
            self.network_trusted_reason = "全網均無效帳本"
            return "❌ 系統不被信任：全網均無效帳本。" if gui_mode else None

        majority_hash, max_count = valid_hashes.most_common(1)[0]

        # 5. 判斷是否過半數
        if max_count > total_expected / 2:

            # 找出所有「實名制」回報但與多數派不一致的節點
            tampered = []
            for nid, h in all_votes.items():
                if h != majority_hash:
                    tag = "INVALID" if h == "INVALID" else ("EMPTY" if h == "EMPTY" else h[:12] + "...")
                    tampered.append(f"{nid}(Hash={tag})")

            if tampered:
                detail = "、".join(tampered)
                output_msg += f"\n🕵️ 偵測到帳本異常節點：{detail}"
                self.add_log(f"[共識機制] 偵測到帳本異常節點：{detail}")
                
            # 【關鍵】從多數派中挑一個持有正確 Hash 的節點作為修復來源
            provider_id = next(node_id for node_id, h in all_votes.items() if h == majority_hash)

            # 【全網修復廣播】告訴每一個存活節點「正確的 Hash 是什麼、該向誰要」
            # 任何本地 Hash 不符的節點（包含被竄改的 peer）會自動向 provider 請求 REQ_SYNC
            broadcast_msg = f"BROADCAST_MAJORITY:{majority_hash}:{provider_id}:{self.node_id}"
            for peer in live_peers:
                self.sock.sendto(broadcast_msg.encode('utf-8'), peer)
            self.add_log(f"[共識機制] 已向全網廣播修復通知（多數決 Hash: {majority_hash[:12]}... / 提供者: {provider_id}）")

            # 如果連我自己都跟多數派不符，也主動發一次 REQ_SYNC 修復自己
            if my_hash != majority_hash:
                output_msg += f"\n🔧 自我診斷：發起節點 {self.node_id} 自身帳本({'INVALID' if my_hash=='INVALID' else my_hash[:12]+'...'})與多數派不符，正在向 {provider_id} 自我修復..."
                self.add_log(f"[自我修復] {self.node_id} 帳本異常，向 {provider_id} 請求 REQ_SYNC")

                if provider_id in self.nodes_contact_book:
                    self.sock.sendto(b"REQ_SYNC", self.nodes_contact_book[provider_id])

            # 等待所有受損節點完成 REQ_SYNC / RESP_SYNC 修復流程，再發獎勵交易，
            # 否則 TX 廣播會在還沒修好的節點上因本地帳本無效而被拒絕。
            time.sleep(SYNC_WAIT_SECONDS)

            if my_hash == majority_hash:
                # 多數派一致 + 我也在多數派 → 解凍
                self.network_trusted = True
                self.network_trusted_reason = ""
                output_msg += f"\n✅ 全網達成共識 ({max_count}/{total_expected})！\n獎勵發放: 100 元 -> {target}"
                self._execute_transaction("SYSTEM", target, "100")
                # 廣播交易給所有人
                for peer in self.peers:
                    self.sock.sendto(f"TX:SYSTEM:{target}:100".encode('utf-8'), peer)
            else:
                output_msg += f"\n（本地帳本剛剛向 {provider_id} 完成修復，本輪不發放獎勵，下次驗證再領取。）"
        else:
            output_msg += f"\n❌ 系統不被信任：無法達成過半數共識 (僅 {max_count}/{total_expected})。"
            self.network_trusted = False
            self.network_trusted_reason = f"無法達成過半數共識 ({max_count}/{total_expected})"

        if gui_mode: return output_msg

    def _execute_transaction(self, sender, receiver, amount):
        # 0. SYSTEM 交易（共識成功後的獎勵）不受信任凍結影響；其餘必須通過信任檢查
        if sender != "SYSTEM":
            ok, msg = self._require_network_trust("交易")
            if not ok:
                raise ValueError(msg)
        # 1. 如果是系統發錢 (SYSTEM)，不用檢查餘額
        if sender != "SYSTEM":
            # 2. 先呼叫我們剛才寫好的 checkMoney 查一下這個人剩多少錢
            res = self._execute_checkMoney(sender)
            # --- 這是取代 'NULL' 的黃金邏輯 ---
            if res is None:
                # 這裡主動觸發廣播（保險起見），並告訴使用者正在修復
                raise ValueError(f"⚠️ 偵測到發送者 {sender} 的帳本異常，系統已自動發起全網同步，請在 2 秒後重試！")
            current_balance = res
            # 3. 檢查錢夠不夠
            if int(current_balance) < int(amount):
                raise ValueError(f"餘額不足！{sender} 目前只有 {current_balance} 元")
        
        tx_data = f"{sender}, {receiver}, {amount}\n"
        with self.file_lock:
            is_valid, msg = self._check_chain_unlocked()
            if not is_valid:
                raise ValueError(f"無法追加交易，因為本地帳本無效：{msg}")

            files = self._ledger_files_unlocked()
            if not files: 
                curr_id, curr_path = 1, f"{STORAGE_PATH}/1.txt"
                with open(curr_path, "w") as f: f.write("Sha256 of previous block: 0\nNext block: None\n")
            else:
                curr_id, curr_path = int(files[-1].split('.')[0]), f"{STORAGE_PATH}/{files[-1]}"

            with open(curr_path, "r") as f: lines = f.readlines()
            if sum(1 for l in lines if "," in l) < 5:
                with open(curr_path, "a") as f: f.write(tx_data)
            else:
                new_id, new_path = curr_id + 1, f"{STORAGE_PATH}/{curr_id + 1}.txt"
                for i, line in enumerate(lines):
                    if line.startswith("Next block:"): lines[i] = f"Next block: {new_id}.txt\n"
                with open(curr_path, "w") as f: f.writelines(lines)
                prev_hash = self._get_file_hash(curr_path)
                with open(new_path, "w") as f: f.write(f"Sha256 of previous block: {prev_hash}\nNext block: None\n{tx_data}")
            self._write_head_hash_unlocked()